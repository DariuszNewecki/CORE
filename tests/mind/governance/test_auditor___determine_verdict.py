"""Verdict-path coverage for ConstitutionalAuditor._determine_verdict.

Pins three original behaviors:
1. Per-file engine crashes flow into crashed_rule_ids via the post-loop
   scan in run_dynamic_rules, and _determine_verdict then returns DEGRADED.
2. A stats computation failure (stats_error key set by the
   get_dynamic_execution_stats exception handler) forces DEGRADED.
3. A genuine ERROR-severity finding without ENFORCEMENT_FAILURE context
   yields FAIL — DEGRADED is reserved for instrument failure.

ADR-156 (#822) adds a fourth precondition, any_unmapped_mapping_required_rules,
and pins:
4. unmapped_rules == 0 does not degrade an otherwise-PASS audit.
5. unmapped_rules > 0 (precondition active) yields DEGRADED.
6. unmapped_rules > 0 together with a BLOCK-severity finding still yields
   DEGRADED, not FAIL — DEGRADED preconditions take precedence over FAIL
   (ADR-156 D1a). This is the regression guard against a future refactor
   moving the new branch after the FAIL-severity check.
7. The policy-error sentinel path ({"_error": True}) is a separate branch
   from the new precondition's own branch — both yield DEGRADED, but for
   different reasons; the new tests below construct a real, valid policy
   dict (no "_error" key) so a DEGRADED result can only be explained by
   the new precondition firing, not by the sentinel path.
8. Advisory-tier exclusion from unmapped_rules is exercised at the
   accounting layer (tests/shared/infrastructure/intent/test_rule_registry.py,
   tests/mind/governance/test_constitutional_auditor_dynamic__get_dynamic_execution_stats.py)
   — not duplicated here. This file only tests _determine_verdict's own
   consumption of the already-computed stats["unmapped_rules"] integer.

#847/#856 add a fifth precondition, any_blocking_unavailable_rules, and pin:
9.  stats["blocking_unavailable_rules"] == 0 does not degrade an
    otherwise-PASS audit.
10. stats["blocking_unavailable_rules"] > 0 (precondition active) yields
    DEGRADED — governor ruling 3.
11. blocking_unavailable_rules > 0 together with a BLOCK-severity finding
    still yields DEGRADED, not FAIL — same precedence rule as unmapped
    (ADR-156 D1a), now proven for the new precondition too.
12. The precondition is opt-in via governed vocabulary, mirroring
    test_unmapped_precondition_absent_from_policy_is_inert.
13. An advisory rule's unavailable dependency (unavailable_rules > 0 but
    blocking_unavailable_rules == 0) does NOT degrade — governor ruling 6.
    Split from blocking_unavailable_rule_ids accounting at the stats layer
    (test_constitutional_auditor_dynamic__get_dynamic_execution_stats.py);
    this file only tests _determine_verdict's own consumption of the
    already-split integer.

load_audit_verdict_policy is patched directly; tests do not depend on
the loader's allowlist or on .intent/ files being parseable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor
from mind.governance.constitutional_auditor_dynamic import run_dynamic_rules
from shared.models import AuditFinding, AuditSeverity


# 2026-06-07 (#572 batch 18): AuditSeverity enum members are INFO / LOW /
# MEDIUM / HIGH / BLOCK — no ``ERROR`` member. Source's _determine_verdict
# constructs ``fail_sevs = {AuditSeverity[name] for name in
# policy["fail_severities"]}`` (auditor.py:163), so the autogen vintage's
# ``"ERROR"`` literal raised KeyError. ``BLOCK`` is the canonical blocking
# severity used by the rule engines.
_BASE_POLICY = {
    "fail_severities": ["BLOCK"],
    "ignored_finding_types": ["ENFORCEMENT_FAILURE"],
    "degraded_on": ["any_crashed_rules", "stats_error"],
}

# ADR-156: a real, valid policy dict with the new precondition active.
# No "_error" key — used to prove DEGRADED results below come from the
# new branch, not the policy-load-failure sentinel branch.
_POLICY_WITH_UNMAPPED = {
    "fail_severities": ["BLOCK"],
    "ignored_finding_types": ["ENFORCEMENT_FAILURE"],
    "degraded_on": [
        "any_crashed_rules",
        "stats_error",
        "any_unmapped_mapping_required_rules",
    ],
}
assert "_error" not in _POLICY_WITH_UNMAPPED

# #847/#856: a real, valid policy dict with any_blocking_unavailable_rules
# active. No "_error" key — same discipline as _POLICY_WITH_UNMAPPED.
_POLICY_WITH_UNAVAILABLE = {
    "fail_severities": ["BLOCK"],
    "ignored_finding_types": ["ENFORCEMENT_FAILURE", "ENFORCEMENT_UNAVAILABLE"],
    "degraded_on": [
        "any_crashed_rules",
        "stats_error",
        "any_blocking_unavailable_rules",
    ],
}
assert "_error" not in _POLICY_WITH_UNAVAILABLE


class TestDetermineVerdict:
    async def test_per_file_crash_yields_degraded(self):
        rule = Mock(rule_id="some.rule.id", engine="ast")
        per_file_crash = AuditFinding(
            check_id="some.rule.id.enforcement_failure",
            severity=AuditSeverity.BLOCK,
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
            severity=AuditSeverity.BLOCK,
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

    # --- ADR-156 (#822): any_unmapped_mapping_required_rules -------------

    def test_policy_error_sentinel_yields_degraded(self):
        """Positive control for item 7: the *original* _error branch,
        distinct from the new precondition's own branch below."""
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value={"_error": True, "reason": "boom"},
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[], stats={}, crashed_rule_ids=set()
            )
        assert verdict == AuditVerdict.DEGRADED

    def test_unmapped_rules_zero_does_not_degrade(self):
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNMAPPED),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"unmapped_rules": 0},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.PASS

    def test_unmapped_rules_positive_yields_degraded_via_new_precondition(self):
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNMAPPED),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"unmapped_rules": 3},
                crashed_rule_ids=set(),
            )
        # _POLICY_WITH_UNMAPPED carries no "_error" key (asserted at module
        # load), so this DEGRADED can only be explained by the new
        # precondition branch — not the policy-load-failure sentinel.
        assert verdict == AuditVerdict.DEGRADED

    def test_unmapped_rules_positive_with_blocking_finding_yields_degraded_not_fail(
        self,
    ):
        """ADR-156 D1a: DEGRADED preconditions precede FAIL. A finding that
        would trigger FAIL on its own must not override an active
        unmapped-mapping-required precondition."""
        finding = AuditFinding(
            check_id="rule.foo",
            severity=AuditSeverity.BLOCK,
            message="Direct DB import in API layer",
            file_path="src/api/routes/x.py",
            context={"some_key": "some_value"},
        )
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNMAPPED),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[finding],
                stats={"unmapped_rules": 2},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.DEGRADED

    def test_unmapped_precondition_absent_from_policy_is_inert(self):
        """If degraded_on does not carry the new word (e.g. an older
        deployed policy), a nonzero unmapped_rules must not degrade —
        the precondition is opt-in via governed vocabulary, not automatic."""
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_BASE_POLICY),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"unmapped_rules": 5},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.PASS

    # --- #847/#856: any_blocking_unavailable_rules ------------------------

    def test_blocking_unavailable_zero_does_not_degrade(self):
        """Governor ruling 3, negative control: no blocking rule reported
        unavailable evidence — an otherwise-clean audit stays PASS."""
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNAVAILABLE),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"blocking_unavailable_rules": 0},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.PASS

    def test_blocking_unavailable_positive_yields_degraded(self):
        """Governor ruling 3: a blocking rule's unavailable dependency/
        evidence makes the audit DEGRADED, never PASS and never FAIL."""
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNAVAILABLE),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"blocking_unavailable_rules": 1},
                crashed_rule_ids=set(),
            )
        # _POLICY_WITH_UNAVAILABLE carries no "_error" key (asserted at
        # module load), so this DEGRADED can only be explained by the new
        # precondition branch.
        assert verdict == AuditVerdict.DEGRADED

    def test_blocking_unavailable_with_blocking_finding_yields_degraded_not_fail(
        self,
    ):
        """Same precedence rule as ADR-156 D1a, now for the new
        precondition: DEGRADED must not be overridden by a finding that
        would trigger FAIL on its own."""
        finding = AuditFinding(
            check_id="rule.foo",
            severity=AuditSeverity.BLOCK,
            message="Direct DB import in API layer",
            file_path="src/api/routes/x.py",
            context={"some_key": "some_value"},
        )
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNAVAILABLE),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[finding],
                stats={"blocking_unavailable_rules": 1},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.DEGRADED

    def test_blocking_unavailable_precondition_absent_from_policy_is_inert(self):
        """Opt-in via governed vocabulary, not automatic — mirrors
        test_unmapped_precondition_absent_from_policy_is_inert."""
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_BASE_POLICY),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"blocking_unavailable_rules": 3},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.PASS

    def test_advisory_unavailable_does_not_degrade_even_with_general_count(self):
        """Governor ruling 6: unavailable_rules (the general, both-tiers
        count) can be nonzero — an advisory rule surfaced its unavailable
        dependency — while blocking_unavailable_rules stays 0. The audit
        must still PASS; the advisory finding remains visible in `findings`
        without forcing degradation."""
        with patch(
            "mind.governance.auditor.load_audit_verdict_policy",
            return_value=dict(_POLICY_WITH_UNAVAILABLE),
        ):
            verdict = ConstitutionalAuditor._determine_verdict(
                findings=[],
                stats={"unavailable_rules": 1, "blocking_unavailable_rules": 0},
                crashed_rule_ids=set(),
            )
        assert verdict == AuditVerdict.PASS
