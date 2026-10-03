"""Valid findings no remediator can act on are delegated, never dropped (D3).

Deep dive 2026-10-03: the audit sensor's actionability filter discarded every
violation on a non-Python file before posting it, e.g. 18-24
``governance.taxonomy.action_supported_by_declaration`` findings per cycle on
``.intent/artifact_types/*.yaml`` — invisible to the loop and the governor.
Governor ruling: inability of the current remediator to act on a target
causes delegation; file type alone does not imply human ownership.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.audit_violation.filter import (
    filter_actionable_violations,
    is_autonomously_remediable_target,
    non_remediable_violations,
)


def _v(file_path: str, rule_id: str = "governance.taxonomy.x") -> dict:
    return {
        "file_path": file_path,
        "rule_id": rule_id,
        "message": "m",
        "severity": "info",
    }


def test_remediable_target_is_python_source() -> None:
    assert is_autonomously_remediable_target("src/a.py")
    assert not is_autonomously_remediable_target(".intent/artifact_types/python.yaml")


def test_non_python_findings_are_delegated_not_actionable() -> None:
    raw = [
        _v("src/a.py"),
        _v(".intent/artifact_types/python.yaml"),
        _v("System"),  # no real target: still dropped
        _v("__symbol_pair__x"),  # placeholder: still dropped
        _v("docs/x.md", rule_id="enforcement/mappings/a.yaml"),  # malformed id
    ]
    assert [v["file_path"] for v in filter_actionable_violations(raw)] == ["src/a.py"]
    assert [v["file_path"] for v in non_remediable_violations(raw)] == [
        ".intent/artifact_types/python.yaml"
    ]


def _sensor(existing: set[str]):  # type: ignore[no-untyped-def]
    from will.workers.audit_violation_sensor import AuditViolationSensor

    sensor = object.__new__(AuditViolationSensor)
    sensor._rule_namespace = "governance"
    sensor._dry_run = False
    sensor._fetch_existing_subjects = AsyncMock(return_value=existing)
    sensor.post_artifact_finding = AsyncMock(return_value="entry-1")
    bb = SimpleNamespace(escalate_finding_to_governor=AsyncMock(return_value=True))
    sensor._core_context = SimpleNamespace(
        registry=SimpleNamespace(get_blackboard_service=AsyncMock(return_value=bb))
    )
    return sensor, bb


@pytest.mark.asyncio
async def test_sensor_posts_and_escalates_with_reason() -> None:
    sensor, bb = _sensor(existing=set())
    count = await sensor._delegate_non_remediable(
        [_v(".intent/artifact_types/python.yaml")], "python"
    )
    assert count == 1
    sensor.post_artifact_finding.assert_awaited_once()
    entry_id, merge = bb.escalate_finding_to_governor.await_args.args
    assert entry_id == "entry-1"
    assert merge["delegation"]["reason"] == "no_autonomous_remediator"
    assert ".yaml" in merge["delegation"]["detail"]


@pytest.mark.asyncio
async def test_sensor_delegates_a_standing_violation_once() -> None:
    subject = "python::governance.taxonomy.x::.intent/artifact_types/python.yaml"
    sensor, bb = _sensor(existing={subject})
    count = await sensor._delegate_non_remediable(
        [_v(".intent/artifact_types/python.yaml")], "python"
    )
    assert count == 0
    sensor.post_artifact_finding.assert_not_awaited()
    bb.escalate_finding_to_governor.assert_not_awaited()


@pytest.mark.asyncio
async def test_remediator_delegates_a_claimed_non_remediable_finding() -> None:
    from will.autonomy.violation_remediator_blackboard import load_open_findings

    yaml_finding = {
        "id": "y1",
        "payload": {"rule": "governance.taxonomy.x", "file_path": "a/b.yaml"},
    }
    py_finding = {"id": "p1", "payload": {"rule": "mapped.rule", "file_path": "a.py"}}
    service = MagicMock()
    service.claim_findings_by_patterns = AsyncMock(
        return_value=[yaml_finding, py_finding]
    )
    service.mark_indeterminate = AsyncMock(return_value=1)
    service.release_claimed_entries = AsyncMock(return_value=0)

    mappable = await load_open_findings(
        service,
        patterns=["python::%"],
        claimed_by="w",
        remediation_map={"mapped.rule": {"ref_id": "fix.x"}},
    )

    assert mappable == [py_finding]
    service.mark_indeterminate.assert_awaited_once_with(["y1"])
    service.release_claimed_entries.assert_not_awaited()
