"""ADR-169 D2: every verdict path degrades when the law evaluated is not the
law of record, and only then.

- shared policy: ``law_drift`` is a known precondition; one helper decides it.
- online: ``ConstitutionalAuditor._determine_verdict``.
- offline: ``run_stateless_audit`` (verdict, findings, law_state in result).
- persisted runs: ``run_and_persist_audit`` writes the auditor's verdict as
  decided -- it used to re-derive it from ``passed`` and save DEGRADED as FAIL.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor
from mind.governance.executable_rule import ExecutableRule
from mind.governance.stateless_audit import run_stateless_audit
from shared.infrastructure.intent.audit_verdict import (
    _KNOWN_PRECONDITIONS,
    _validate_policy,
    law_drift_degrades,
)
from shared.infrastructure.intent.law_state import LawState


_POLICY = {
    "fail_severities": ["BLOCK"],
    "ignored_finding_types": ["ENFORCEMENT_FAILURE", "LAW_DRIFT"],
    "degraded_on": ["any_crashed_rules", "law_drift"],
}
_POLICY_WITHOUT_LAW_DRIFT = {**_POLICY, "degraded_on": ["any_crashed_rules"]}

_DRIFT = LawState(
    relationship="DRIFT",
    head_sha="a" * 40,
    record_digest="r",
    evaluated_digest="e",
    drift_paths=[".intent/rules/x.json"],
)
_MATCH = LawState(relationship="MATCH", head_sha="a" * 40)


# --- shared policy ---------------------------------------------------------


def test_law_drift_is_a_known_precondition() -> None:
    assert "law_drift" in _KNOWN_PRECONDITIONS
    _validate_policy(dict(_POLICY))  # must not raise


@pytest.mark.parametrize(
    ("relationship", "expected"),
    [("MATCH", False), ("DRIFT", True), ("UNKNOWN", True), (None, True)],
)
def test_law_drift_degrades_unless_match(relationship, expected) -> None:
    assert law_drift_degrades(_POLICY, relationship) is expected


def test_policy_without_law_drift_never_degrades_on_it() -> None:
    assert law_drift_degrades(_POLICY_WITHOUT_LAW_DRIFT, "DRIFT") is False


# --- online auditor --------------------------------------------------------


def _verdict(law_relationship, findings=()):
    with patch(
        "mind.governance.auditor.load_audit_verdict_policy",
        return_value=dict(_POLICY),
    ):
        return ConstitutionalAuditor._determine_verdict(
            list(findings),
            stats={},
            crashed_rule_ids=set(),
            law_relationship=law_relationship,
        )


def test_online_match_can_pass() -> None:
    assert _verdict("MATCH") == AuditVerdict.PASS


def test_online_drift_is_degraded() -> None:
    assert _verdict("DRIFT") == AuditVerdict.DEGRADED


def test_online_unobserved_law_is_degraded_not_pass() -> None:
    assert _verdict(None) == AuditVerdict.DEGRADED


# --- offline (stateless) audit ----------------------------------------------


def _rule() -> ExecutableRule:
    return ExecutableRule(
        rule_id="some.rule", engine="regex_gate", params={}, enforcement="blocking"
    )


async def _offline(law: LawState, tmp_path: Path) -> dict:
    with (
        patch("mind.governance.stateless_audit.observe_law_state", return_value=law),
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=[_rule()],
        ),
        patch("mind.governance.stateless_audit._count_declared_rules", return_value=1),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], {"some.rule"}, {})),
        ),
        patch(
            "mind.governance.stateless_audit.load_audit_verdict_policy",
            return_value=dict(_POLICY),
        ),
    ):
        return await run_stateless_audit(MagicMock(), tmp_path)


async def test_offline_drift_is_degraded_and_names_the_path(tmp_path: Path) -> None:
    result = await _offline(_DRIFT, tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False
    assert result["law_state"]["relationship"] == "DRIFT"
    drift = [f for f in result["findings"] if f["check_id"] == "governance.law_drift"]
    assert [f["file_path"] for f in drift] == [".intent/rules/x.json"]


async def test_offline_match_passes_and_states_its_law(tmp_path: Path) -> None:
    result = await _offline(_MATCH, tmp_path)
    assert result["verdict"] == "PASS"
    assert result["law_state"]["relationship"] == "MATCH"


# --- persisted runs: DEGRADED is not saved as FAIL ---------------------------


async def test_persisted_run_keeps_degraded_verdict() -> None:
    from will.governance import audit_runner

    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    results = {
        "findings": [],
        "passed": False,
        "verdict": AuditVerdict.DEGRADED,
        "law_state": _DRIFT.to_dict(),
    }
    with (
        patch.object(
            audit_runner, "run_audit_workflow", new=AsyncMock(return_value=results)
        ),
        patch.object(audit_runner, "_record_run_observation", new=AsyncMock()),
    ):
        out = await audit_runner.run_and_persist_audit(
            SimpleNamespace(), session, run_id="00000000-0000-0000-0000-000000000001"
        )
    assert out["verdict"] == "DEGRADED"
    params = session.execute.await_args.args[1]
    assert params["verdict"] == "DEGRADED"
