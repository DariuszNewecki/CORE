"""Tests for run_filtered_audit — rule failure surfacing.

Verifies that a rule whose execute_rule() raises an exception surfaces a
governance.audit_engine.rule_evaluation_failed finding in the returned
findings list instead of being silently swallowed into the warning log.

Closes the gap identified post-ADR-134: a broken rule left no
blackboard-visible trace, making the governance engine untrustworthy.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.filtered_audit import run_filtered_audit
from shared.models.audit_models import AuditFinding, AuditSeverity


def _make_rule(
    rule_id: str = "test.rule.stub", policy_id: str = "test_policy"
) -> MagicMock:
    rule = MagicMock()
    rule.rule_id = rule_id
    rule.policy_id = policy_id
    rule.is_context_level = False
    return rule


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.repo_path = "/fake/repo"
    ctx.policies = []
    ctx.enforcement_loader = MagicMock()
    ctx.reload_governance = MagicMock()
    ctx.invalidate_file_cache = MagicMock()
    ctx.sweep_llm_gate_cache = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_failed_rule_emits_finding() -> None:
    """A rule that raises during execute_rule must produce a HIGH finding."""
    rule = _make_rule("test.rule.will_fail")
    ctx = _make_context()

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            new_callable=AsyncMock,
            side_effect=RuntimeError("engine exploded"),
        ),
    ):
        findings, executed_ids, stats = await run_filtered_audit(ctx)

    assert stats["failed_rules"] == 1
    assert rule.rule_id not in executed_ids

    failure_findings = [
        f
        for f in findings
        if f["check_id"] == "governance.audit_engine.rule_evaluation_failed"
    ]
    assert len(failure_findings) == 1
    f = failure_findings[0]
    assert f["severity"] == "high"
    assert "test.rule.will_fail" in f["message"]
    assert "engine exploded" in f["message"]
    assert f["context"]["rule_id"] == "test.rule.will_fail"
    assert f["context"]["error_type"] == "RuntimeError"
    assert f["evidence_class"] == "attested"


@pytest.mark.asyncio
async def test_failed_rule_does_not_abort_remaining_rules() -> None:
    """A failing rule must not prevent subsequent rules from running."""
    failing_rule = _make_rule("test.rule.broken")
    good_rule = _make_rule("test.rule.healthy")
    ctx = _make_context()

    good_finding = AuditFinding(
        check_id="test.rule.healthy",
        severity=AuditSeverity.LOW,
        message="A legitimate finding",
    )

    async def _execute(rule, *args, **kwargs):
        if rule.rule_id == "test.rule.broken":
            raise ValueError("broken rule engine")
        return [good_finding]

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[failing_rule, good_rule],
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            side_effect=_execute,
        ),
    ):
        findings, _executed_ids, stats = await run_filtered_audit(ctx)

    assert stats["failed_rules"] == 1
    assert stats["executed_rules"] == 1
    check_ids = {f["check_id"] for f in findings}
    assert "governance.audit_engine.rule_evaluation_failed" in check_ids
    assert "test.rule.healthy" in check_ids


@pytest.mark.asyncio
async def test_no_findings_when_all_rules_succeed() -> None:
    """When all rules execute cleanly no failure finding is emitted."""
    rule = _make_rule("test.rule.clean")
    ctx = _make_context()

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        findings, _executed, stats = await run_filtered_audit(ctx)

    assert stats["failed_rules"] == 0
    failure_findings = [
        f
        for f in findings
        if f["check_id"] == "governance.audit_engine.rule_evaluation_failed"
    ]
    assert failure_findings == []
