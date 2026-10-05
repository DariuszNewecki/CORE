"""A filtered online audit decides its verdict from its findings.

`run_sync_audit`'s filtered branch (POST /v1/audit/runs with rule/policy/file
filters, i.e. `core-admin code audit --rule X`) hard-coded ``passed: True``
and no verdict, so the API answered PASS -- and the CLI exited 0 -- even when
the audited rule returned a blocking finding. The verdict was rebuilt from a
yes/no flag instead of being decided.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infrastructure.intent.law_state import LawState
from will.governance import audit_runner


_POLICY = {
    "fail_severities": ["BLOCK"],
    "ignored_finding_types": [
        "ENFORCEMENT_FAILURE",
        "ENFORCEMENT_UNAVAILABLE",
        "LAW_DRIFT",
    ],
    "degraded_on": [
        "any_crashed_rules",
        "any_blocking_unavailable_rules",
        "law_drift",
    ],
}
_MATCH = LawState(relationship="MATCH", head_sha="a" * 40)


def _finding(severity: str, finding_type: str | None = None) -> dict:
    context = {"finding_type": finding_type} if finding_type else {}
    return {
        "check_id": "some.rule",
        "severity": severity,
        "message": "m",
        "file_path": "src/x.py",
        "context": context,
    }


async def _filtered(findings: list[dict], stats: dict | None = None) -> dict:
    context = SimpleNamespace(
        auditor_context=SimpleNamespace(
            load_knowledge_graph=AsyncMock(),
            intent_repo=SimpleNamespace(root="/repo/.intent"),
            db_session=None,
            force_llm=False,
        )
    )
    with (
        patch.object(
            audit_runner,
            "run_filtered_audit",
            new=AsyncMock(
                return_value=(findings, {"some.rule"}, stats or {"failed_rules": 0})
            ),
        ),
        patch.object(audit_runner, "observe_law_state", return_value=_MATCH),
        patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY),
        ),
    ):
        return await audit_runner.run_sync_audit(
            context, MagicMock(), rule_ids=["some.rule"]
        )


async def test_blocking_finding_fails_a_filtered_audit() -> None:
    result = await _filtered([_finding("block")])
    assert result["verdict"] == "FAIL"
    assert result["passed"] is False


async def test_clean_filtered_audit_passes() -> None:
    result = await _filtered([_finding("medium")])
    assert result["verdict"] == "PASS"
    assert result["passed"] is True


async def test_crashed_rule_degrades_a_filtered_audit() -> None:
    result = await _filtered([_finding("high")], stats={"failed_rules": 1})
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False


@pytest.mark.parametrize(
    "finding_type", ["ENFORCEMENT_FAILURE", "ENFORCEMENT_UNAVAILABLE"]
)
async def test_unevaluated_rule_degrades_never_fails(finding_type: str) -> None:
    result = await _filtered([_finding("block", finding_type)])
    assert result["verdict"] == "DEGRADED"
