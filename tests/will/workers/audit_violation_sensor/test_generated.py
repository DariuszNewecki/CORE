"""Tests for AuditViolationSensor.

2026-06-07 (#572 Cat B batch 19): the autogen vintage of this file was
entirely speculative — it defined a local ``class AuditViolationSensor:
pass`` placeholder (instead of importing the real worker), wired up
mock factory functions that returned classes with no actual methods,
asserted on call_count attributes that would have raised AttributeError
on the placeholder mocks, and used MagicMock without importing it
(NameError on the only test). The file was effectively dead — nothing
referenced the real ``will.workers.audit_violation_sensor`` symbol.

Replaced with a minimal smoke test against the real class. The worker
takes ``(core_context, declaration_name, rule_namespace,
dry_run=True)`` and inherits from the Worker base. A deeper behavioural
test belongs in an integration suite where the blackboard / consequence
log services and a real session provider are available; the smoke test
pins the import surface and the constructor signature without taking
on integration-level setup.
"""

from __future__ import annotations

from unittest.mock import Mock

from will.workers.audit_violation_sensor import AuditViolationSensor


# ID: 188f3848-3255-4c07-856a-c1e7166ef151
def test_audit_violation_sensor_constructs_with_required_args():
    """AuditViolationSensor.__init__ requires
    (core_context, declaration_name, rule_namespace) — the optional
    ``dry_run`` defaults to True so destructive runs are opt-in.

    ``declaration_name`` is looked up against
    ``.intent/workers/<name>.yaml`` at construction time, so it must be
    a name that has a real declaration on disk. ``audit_violation_sensor``
    is the worker's own canonical name and is the only declaration
    guaranteed to exist for this worker class."""
    ctx = Mock()
    sensor = AuditViolationSensor(
        core_context=ctx,
        declaration_name="audit_violation_sensor",
        rule_namespace="example_ns",
    )
    assert sensor.declaration_name == "audit_violation_sensor"


import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ID: 8d3de624-fd25-41f7-8521-6b611519bf3a
def test_AuditViolationSensor():
    core_context = MagicMock()
    core_context.auditor_context = MagicMock()
    core_context.auditor_context.repo_path = Path("/repo")
    core_context.registry = MagicMock()

    declaration = {"mandate": {"scope": {"artifact_type": ["python"]}}}

    # Build the instance without invoking the base Worker.__init__ (which
    # touches the read-only `_declaration` property).
    sensor = AuditViolationSensor.__new__(AuditViolationSensor)

    from shared.workers.base import Worker

    with patch.object(Worker, "_load_declaration", return_value=declaration):
        # Manually reproduce the minimal state __init__ would have set.
        sensor._core_context = core_context
        sensor._behind_cycles = 0
        sensor._rule_namespace = "purity"
        sensor._dry_run = True
        sensor._declaration = declaration
        sensor._artifact_type = "python"

    with patch(
        "will.workers.audit_violation_sensor.get_intent_repository"
    ) as mock_get_repo:
        repo = MagicMock()
        repo.get_artifact_type.return_value = MagicMock(
            content={"discovery": ["**/*.py"]}
        )
        repo._rule_index = {"purity.no_print": {}}
        mock_get_repo.return_value = repo

        sensor.post_heartbeat = AsyncMock()
        sensor.post_report = AsyncMock()

        with (
            patch(
                "will.workers.audit_violation_sensor.check_audited_commit",
                new=AsyncMock(return_value=(MagicMock(as_payload=lambda: {}), 0)),
            ),
            patch(
                "will.workers.audit_violation_sensor.law_glob",
                return_value=iter(["a.py", "b.py"]),
            ),
            patch(
                "will.workers.audit_violation_sensor.normalize_audit_findings",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "will.workers.audit_violation_sensor.filter_actionable_violations",
                return_value=[],
            ),
            patch(
                "will.workers.audit_violation_sensor.non_remediable_violations",
                return_value=[],
            ),
            patch(
                "will.workers.audit_violation_sensor.drain_cleared_findings",
                new=AsyncMock(return_value=None),
            ),
        ):
            bb_svc = AsyncMock()
            bb_svc.resolve_dry_run_entries_for_namespace = AsyncMock(return_value=0)
            core_context.registry.get_blackboard_service = AsyncMock(
                return_value=bb_svc
            )

            asyncio.run(sensor.run())

    sensor.post_heartbeat.assert_awaited()
    sensor.post_report.assert_awaited()
    assert sensor._rule_namespace == "purity"
    assert sensor._dry_run is True
    assert sensor._artifact_type == "python"



import pytest


@pytest.mark.asyncio
# ID: b3db4c9e-acfc-4713-ae2c-60ce6802bc0b
async def test_AuditViolationSensor_run():
    core_context = MagicMock()
    auditor_context = MagicMock()
    auditor_context.repo_path = Path("/repo")
    core_context.auditor_context = auditor_context

    bb_svc = AsyncMock()
    bb_svc.resolve_dry_run_entries_for_namespace = AsyncMock(return_value=0)
    consequence_svc = AsyncMock()
    consequence_svc.find_cause_for_file = AsyncMock(
        return_value={"causing_proposal_id": None, "causing_commit_sha": None}
    )

    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_svc)
    registry.get_consequence_log_service = AsyncMock(return_value=consequence_svc)
    core_context.registry = registry

    sensor = AuditViolationSensor.__new__(AuditViolationSensor)
    sensor._core_context = core_context
    sensor._behind_cycles = 0
    sensor._rule_namespace = "ns"
    sensor._dry_run = True
    sensor._artifact_type = "python"
    sensor._config = {}
    sensor._declaration = {"mandate": {"scope": {"artifact_type": ["python"]}}}

    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()
    sensor.post_artifact_finding = AsyncMock()
    sensor._resolve_rule_ids = MagicMock(return_value=["R1"])
    sensor._fetch_existing_subjects = AsyncMock(return_value=set())
    sensor._delegate_non_remediable = AsyncMock(return_value=0)

    intent_repo = MagicMock()
    intent_repo.get_artifact_type = MagicMock(
        return_value=MagicMock(content={"discovery": ["*.py"]})
    )
    intent_repo._rule_index = {"R1": object()}

    audited = MagicMock()
    audited.as_payload = MagicMock(return_value={"audited": True})

    violations = [
        {
            "rule_id": "R1",
            "file_path": "src/foo.py",
            "line_number": 10,
            "message": "violation",
            "severity": "high",
        }
    ]

    with (
        patch(
            "will.workers.audit_violation_sensor.check_audited_commit",
            AsyncMock(return_value=(audited, 0)),
        ),
        patch(
            "will.workers.audit_violation_sensor.get_intent_repository",
            MagicMock(return_value=intent_repo),
        ),
        patch(
            "will.workers.audit_violation_sensor.law_glob",
            MagicMock(return_value=[Path("/repo/src/foo.py")]),
        ),
        patch(
            "will.workers.audit_violation_sensor.normalize_audit_findings",
            AsyncMock(return_value=violations),
        ),
        patch(
            "will.workers.audit_violation_sensor.filter_actionable_violations",
            MagicMock(return_value=violations),
        ),
        patch(
            "will.workers.audit_violation_sensor.non_remediable_violations",
            MagicMock(return_value=[]),
        ),
        patch(
            "will.workers.audit_violation_sensor.drain_cleared_findings",
            AsyncMock(return_value=None),
        ),
        patch(
            "will.workers.audit_violation_sensor._route_to",
            MagicMock(return_value=None),
        ),
    ):
        await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    sensor.post_artifact_finding.assert_awaited_once()
    sensor.post_report.assert_awaited()
    complete_call = sensor.post_report.await_args
    assert complete_call.kwargs["subject"] == "audit_violation_sensor.run.complete"
    assert complete_call.kwargs["payload"]["posted"] == 1
    auditor_context.reload_governance.assert_called_once()
    auditor_context.invalidate_file_cache.assert_called_once()
