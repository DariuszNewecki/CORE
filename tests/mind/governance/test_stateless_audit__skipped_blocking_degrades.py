"""#907 -- a skipped BLOCKING rule makes the stateless verdict DEGRADED.

Before this fix, run_stateless_audit's verdict branch (#847/#856) only
consulted *findings*. `skipped_rules` was populated and never read again,
so `core-admin code audit --offline --severity=block` rendered an
unqualified PASS while three blocking rules (two knowledge_gate
capability-taxonomy rules + runtime.worker_max_interval_within_observed)
were never evaluated. Reproduced on CORE at 429c0f40 before the fix.

Governor ruling (2026-09-18):

1. An audit that skips a blocking rule MUST NOT return PASS.
2. The verdict is DEGRADED, not FAIL -- absence of evidence is distinct
   from a demonstrated violation.
5. Skipped advisory/reporting rules stay visible but do not by themselves
   prevent PASS.
6. "Not evaluated" is never counted or presented as "passed".

The precondition reused is the governed `any_blocking_unavailable_rules`
entry of `.intent/enforcement/config/audit_verdict.yaml`'s degraded_on --
the same one ConstitutionalAuditor._determine_verdict reads -- so this is
not a second private verdict vocabulary.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.executable_rule import ExecutableRule
from mind.governance.stateless_audit import run_stateless_audit


def _rule(rule_id: str, engine: str, enforcement: str) -> ExecutableRule:
    return ExecutableRule(
        rule_id=rule_id, engine=engine, params={}, enforcement=enforcement
    )


def _genuine_violation(rule_id: str) -> dict:
    return {
        "check_id": rule_id,
        "severity": "BLOCK",
        "evidence_class": "PROVEN",
        "message": "a real constitutional violation",
        "file_path": "src/x.py",
        "line_number": 1,
        "context": {"some_key": "some_value"},
        "details": {"some_key": "some_value"},
    }


async def _run(
    rules: list[ExecutableRule],
    tmp_path: Path,
    findings: list[dict] | None = None,
) -> dict:
    """Run with every runnable rule reported as cleanly executed."""
    runnable = {
        r.rule_id
        for r in rules
        if r.engine not in {"knowledge_gate", "llm_gate"}
        and r.rule_id != "runtime.worker_max_interval_within_observed"
    }
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=len(rules),
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=(findings or [], runnable, {})),
        ),
    ):
        return await run_stateless_audit(intent_repo, tmp_path)


async def test_no_skips_and_no_blocking_findings_is_pass(tmp_path: Path) -> None:
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule("b.re", "regex_gate", "reporting"),
    ]
    result = await _run(rules, tmp_path)
    assert result["verdict"] == "PASS"
    assert result["passed"] is True
    assert result["skipped_rules"] == []
    assert result["stats"]["skipped_blocking_rules_count"] == 0
    assert result["stats"]["skipped_blocking_rule_ids"] == []


async def test_advisory_only_skips_still_pass_with_visible_skip_info(
    tmp_path: Path,
) -> None:
    """Ruling 5: skipped advisory/reporting rules are visible, not gating."""
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule("modularity.unix_philosophy", "llm_gate", "advisory"),
        _rule("purity.no_orphan_files", "knowledge_gate", "reporting"),
    ]
    result = await _run(rules, tmp_path)
    assert result["verdict"] == "PASS"
    assert result["passed"] is True
    by_id = {e["rule_id"]: e for e in result["skipped_rules"]}
    assert by_id["modularity.unix_philosophy"]["enforcement"] == "advisory"
    assert by_id["purity.no_orphan_files"]["enforcement"] == "reporting"
    assert result["stats"]["skipped_rules_count"] == 2
    assert result["stats"]["skipped_blocking_rules_count"] == 0


async def test_one_skipped_blocking_rule_is_degraded_not_pass(tmp_path: Path) -> None:
    """Rulings 1+2: one skipped blocking rule -> DEGRADED, never PASS."""
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule(
            "capability.taxonomy.roles_require_canonical_capabilities",
            "knowledge_gate",
            "blocking",
        ),
    ]
    result = await _run(rules, tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False
    assert result["stats"]["skipped_blocking_rules_count"] == 1
    assert result["stats"]["skipped_blocking_rule_ids"] == [
        "capability.taxonomy.roles_require_canonical_capabilities"
    ]


async def test_mixed_advisory_and_blocking_skips_is_degraded(tmp_path: Path) -> None:
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule("modularity.unix_philosophy", "llm_gate", "advisory"),
        _rule("purity.no_orphan_files", "knowledge_gate", "reporting"),
        _rule(
            "runtime.worker_max_interval_within_observed", "runtime_gate", "blocking"
        ),
    ]
    result = await _run(rules, tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False
    assert result["stats"]["skipped_rules_count"] == 3
    assert result["stats"]["skipped_blocking_rules_count"] == 1
    assert result["stats"]["skipped_blocking_rule_ids"] == [
        "runtime.worker_max_interval_within_observed"
    ]


async def test_genuine_blocking_violation_with_no_skips_remains_fail(
    tmp_path: Path,
) -> None:
    rules = [_rule("a.ast", "ast_gate", "blocking")]
    result = await _run(rules, tmp_path, findings=[_genuine_violation("a.ast")])
    assert result["verdict"] == "FAIL"
    assert result["passed"] is False


async def test_skipped_blocking_rules_are_not_counted_as_executed(
    tmp_path: Path,
) -> None:
    """Ruling 6: not evaluated != passed. Skipped IDs never appear in
    executed_rule_ids and never inflate runnable_rules."""
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule(
            "capability.taxonomy.roles_require_canonical_capabilities",
            "knowledge_gate",
            "blocking",
        ),
    ]
    result = await _run(rules, tmp_path)
    assert result["executed_rule_ids"] == ["a.ast"]
    assert result["stats"]["runnable_rules"] == 1
    assert result["stats"]["total_rules"] == 2
    assert (
        "capability.taxonomy.roles_require_canonical_capabilities"
        not in result["executed_rule_ids"]
    )


async def test_skipped_entries_expose_id_enforcement_and_reason(
    tmp_path: Path,
) -> None:
    """Ruling 4: every skipped entry carries rule ID, severity (enforcement
    level) and the reason it was not evaluated -- self-describing JSON."""
    rules = [
        _rule(
            "capability.taxonomy.roles_require_canonical_capabilities",
            "knowledge_gate",
            "blocking",
        ),
        _rule(
            "runtime.worker_max_interval_within_observed", "runtime_gate", "blocking"
        ),
        _rule("modernization.legacy_scars", "llm_gate", "advisory"),
    ]
    result = await _run(rules, tmp_path)
    for entry in result["skipped_rules"]:
        assert set(entry) == {"rule_id", "engine", "enforcement", "reason"}
        assert entry["reason"]
    by_id = {e["rule_id"]: e for e in result["skipped_rules"]}
    assert (
        by_id["capability.taxonomy.roles_require_canonical_capabilities"]["enforcement"]
        == "blocking"
    )
    assert (
        "knowledge graph"
        in by_id["capability.taxonomy.roles_require_canonical_capabilities"]["reason"]
    )
    assert (
        by_id["runtime.worker_max_interval_within_observed"]["enforcement"]
        == "blocking"
    )
    assert (
        "db_session" in by_id["runtime.worker_max_interval_within_observed"]["reason"]
    )
    assert by_id["modernization.legacy_scars"]["enforcement"] == "advisory"


async def test_degraded_precondition_is_governed_not_hardcoded(tmp_path: Path) -> None:
    """The skip->DEGRADED link reads audit_verdict.yaml's degraded_on. If a
    governor removed any_blocking_unavailable_rules from that list, the
    stateless path would follow -- proving there is no private vocabulary."""
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule("x.graph", "knowledge_gate", "blocking"),
    ]
    with patch(
        "mind.governance.stateless_audit.load_audit_verdict_policy",
        return_value={
            "fail_severities": ["BLOCK"],
            "ignored_finding_types": ["ENFORCEMENT_FAILURE", "ENFORCEMENT_UNAVAILABLE"],
            "degraded_on": ["any_crashed_rules"],
        },
    ):
        result = await _run(rules, tmp_path)
    assert result["verdict"] == "PASS"


async def test_reproduced_offline_case_no_longer_passes(tmp_path: Path) -> None:
    """The exact #907 shape: every runnable rule clean, the three blocking
    rules CORE's own law maps to knowledge_gate/runtime_gate-with-db skipped,
    eight reporting/advisory rules skipped alongside them."""
    rules = [
        _rule("a.ast", "ast_gate", "blocking"),
        _rule(
            "capability.taxonomy.resources_provide_canonical_capabilities",
            "knowledge_gate",
            "blocking",
        ),
        _rule(
            "capability.taxonomy.roles_require_canonical_capabilities",
            "knowledge_gate",
            "blocking",
        ),
        _rule(
            "runtime.worker_max_interval_within_observed", "runtime_gate", "blocking"
        ),
        _rule("architecture.mind.no_execution_semantics", "llm_gate", "reporting"),
        _rule("data.integrity.vector_sync", "knowledge_gate", "reporting"),
        _rule("purity.logic_conservation", "llm_gate", "reporting"),
        _rule("purity.no_ast_duplication", "knowledge_gate", "reporting"),
        _rule("purity.no_orphan_files", "knowledge_gate", "reporting"),
        _rule("purity.no_semantic_duplication", "knowledge_gate", "reporting"),
        _rule("modernization.legacy_scars", "llm_gate", "advisory"),
        _rule("modularity.unix_philosophy", "llm_gate", "advisory"),
    ]
    result = await _run(rules, tmp_path)
    assert result["verdict"] != "PASS"
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False
    assert result["stats"]["skipped_rules_count"] == 11
    assert result["stats"]["skipped_blocking_rules_count"] == 3
    assert result["stats"]["skipped_blocking_rule_ids"] == [
        "capability.taxonomy.resources_provide_canonical_capabilities",
        "capability.taxonomy.roles_require_canonical_capabilities",
        "runtime.worker_max_interval_within_observed",
    ]
