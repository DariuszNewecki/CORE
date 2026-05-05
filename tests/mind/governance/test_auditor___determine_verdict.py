"""Verdict-path coverage for ConstitutionalAuditor._determine_verdict.

Pins three behaviors:
1. Per-file engine crashes flow into crashed_rule_ids via the post-loop
   scan in run_dynamic_rules, and _determine_verdict then returns DEGRADED.
2. A stats computation failure (stats_error key set by the
   get_dynamic_execution_stats exception handler) forces DEGRADED.
3. A genuine ERROR-severity finding without ENFORCEMENT_FAILURE context
   yields FAIL — DEGRADED is reserved for instrument failure.

load_audit_verdict_policy is patched directly; tests do not depend on
the loader's allowlist or on .intent/ files being parseable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor
from mind.governance.constitutional_auditor_dynamic import run_dynamic_rules
from shared.models import AuditFinding, AuditSeverity


_BASE_POLICY = {
    "fail_severities": ["ERROR"],
    "ignored_finding_types": ["ENFORCEMENT_FAILURE"],
    "degraded_on": ["any_crashed_rules", "stats_error"],
}


class TestDetermineVerdict:
    async def test_per_file_crash_yields_degraded(self):
        rule = Mock(rule_id="some.rule.id", engine="ast")
        per_file_crash = AuditFinding(
            check_id="some.rule.id.enforcement_failure",
            severity=AuditSeverity.ERROR,
            message="Rule crashed on file foo.py: boom",
            file_path="foo.py",
            context={
                "finding_type": "ENFORCEMENT_FAILURE",
                "engine": "ast",
                "policy_id": "p",
                "exception_type": "RuntimeError",
                "exception_message": "boom",
            },
        )

        executed_rule_ids: set[str] = set()
        crashed_rule_ids: set[str] = set()

        with (
            patch(
                "mind.governance.constitutional_auditor_dynamic"
                ".extract_executable_rules",
                return_value=[rule],
            ),
            patch(
                "mind.logic.engines.registry.EngineRegistry.get",
                return_value=Mock(),
            ),
            patch(
                "mind.governance.rule_executor.execute_rule",
                new=AsyncMock(return_value=[per_file_crash]),
            ),
        ):
            findings = await run_dynamic_rules(
                Mock(policies={}, enforcement_loader=Mock()),
                executed_rule_ids=executed_rule_ids,
                crashed_rule_ids=crashed_rule_ids,
            )

        assert "some.rule.id" in crashed_rule_ids, (
            "Post-loop scan must lift the ENFORCEMENT_FAILURE check_id "
            "into crashed_rule_ids."
        )

        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_BASE_POLICY),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings, stats={}, crashed_rule_ids=crashed_rule_ids
            )
        assert verdict == AuditVerdict.DEGRADED

    def test_stats_error_yields_degraded(self):
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_BASE_POLICY),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"stats_error": "RuntimeError: something broke"},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.DEGRADED

    def test_genuine_blocking_violation_yields_fail(self):
        finding = AuditFinding(
            check_id="rule.foo",
            severity=AuditSeverity.ERROR,
            message="Direct DB import in API layer",
            file_path="src/api/routes/x.py",
            context={"some_key": "some_value"},
        )
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_BASE_POLICY),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[finding],
                stats={},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.FAIL
