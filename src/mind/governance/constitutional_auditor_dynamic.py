# src/mind/governance/constitutional_auditor_dynamic.py

"""
Dynamic Rule Execution Integration.

HARDENING (V2.5.0):
- P0.1: Rule crashes now produce ENFORCEMENT_FAILURE findings (never silently pass).
- P0.2: Stats include total declared rules, unmapped rules, crashed rules.
- Audit truthfulness: unknown ≠ pass, crash ≠ pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mind.governance.rule_extractor import extract_executable_rules
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: 0a059dc3-c748-46f0-8b5e-40036e5085d6
async def run_dynamic_rules(
    context: AuditorContext,
    *,
    executed_rule_ids: set[str],
    crashed_rule_ids: set[str] | None = None,
) -> list:
    """Execute all rules via their declared engines.

    HARDENING: Crashing rules now produce ENFORCEMENT_FAILURE findings
    instead of being silently swallowed. A crashing rule MUST NOT be
    indistinguishable from a passing rule.

    Args:
        context: AuditorContext with policies, enforcement loader, paths.
        executed_rule_ids: Mutable set — populated with IDs of rules that ran.
        crashed_rule_ids: Mutable set — populated with IDs of rules that crashed.
            If None, an internal set is used (backward compat).
    """
    # DEFERRED IMPORT: Break circular loop
    from mind.governance.rule_executor import execute_rule
    from mind.logic.engines.registry import EngineRegistry

    if crashed_rule_ids is None:
        crashed_rule_ids = set()

    all_findings = []
    executable_rules = extract_executable_rules(
        context.policies, context.enforcement_loader
    )

    # ADR-076 D6 standing gate: surface zero-match enforcing per-file
    # rules as SCOPE_INERT findings before the rule loop. The D5 walker
    # derivation closed the #480 silent-inert vector at its root, but a
    # rule whose scope drifts to a pattern matching no files (typo, dir
    # rename, dead glob) still wouldn't be caught until someone notices
    # it never fires. Promoting the D6 firing-coverage assertion into the
    # audit driver makes such drift visible in the next audit verdict
    # rather than discoverable months later.
    all_findings.extend(_check_per_file_scope_coverage(context, executable_rules))

    executed_count = 0
    skipped_stub_count = 0

    for rule in executable_rules:
        try:
            engine = EngineRegistry.get(rule.engine)
            engine_type_name = type(engine).__name__

            if rule.engine == "llm_gate" and "stub" in engine_type_name.lower():
                executed_rule_ids.add(rule.rule_id)
                executed_count += 1
                skipped_stub_count += 1
                continue

            executed_rule_ids.add(rule.rule_id)
            executed_count += 1
            # ADR-043 D3: pass the running findings accumulator so rules
            # with requires_findings_from can narrow their per-file scope
            # to files already flagged by their preconditions. Rules are
            # topologically sorted by extract_executable_rules, so
            # preconditions are guaranteed to be in all_findings before
            # any dependent rule executes.
            findings = await execute_rule(rule, context, prior_findings=all_findings)
            all_findings.extend(findings)

        except Exception as e:
            # HARDENING P0.1: Rule crash → enforcement-failure finding.
            # A crashing rule is NOT a passing rule. It is a governance
            # system failure that must be visible in the audit verdict.
            crashed_rule_ids.add(rule.rule_id)
            executed_rule_ids.add(rule.rule_id)
            executed_count += 1

            logger.error(
                "ENFORCEMENT_FAILURE: Rule %s crashed during execution: %s",
                rule.rule_id,
                e,
                exc_info=True,
            )

            all_findings.append(
                AuditFinding(
                    check_id=rule.rule_id,
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"ENFORCEMENT_FAILURE: Rule crashed during execution: {e}. "
                        f"This rule's compliance status is UNKNOWN — "
                        f"treat as non-compliant until fixed."
                    ),
                    file_path=None,
                    context={
                        "finding_type": "ENFORCEMENT_FAILURE",
                        "engine": rule.engine,
                        "policy_id": rule.policy_id,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                )
            )

    # HARDENING P0.1 (completion): per-file engine crashes in
    # execute_rule emit ENFORCEMENT_FAILURE findings but do not
    # populate crashed_rule_ids from here. Aggregate their rule_ids
    # so _determine_verdict correctly returns DEGRADED.
    # Set semantics make this idempotent with the outer handler above.
    _ENFORCEMENT_FAILURE_SUFFIX = ".enforcement_failure"
    for finding in all_findings:
        ctx = getattr(finding, "context", None)
        check_id = getattr(finding, "check_id", "") or ""
        if (
            isinstance(ctx, dict)
            and ctx.get("finding_type") == "ENFORCEMENT_FAILURE"
            and check_id.endswith(_ENFORCEMENT_FAILURE_SUFFIX)
        ):
            rule_id = check_id[: -len(_ENFORCEMENT_FAILURE_SUFFIX)]
            if rule_id:
                crashed_rule_ids.add(rule_id)

    logger.info(
        "Dynamic Rule Execution: Completed %d rules (Skipped %d stubs, %d crashed)",
        executed_count,
        skipped_stub_count,
        len(crashed_rule_ids),
    )
    return all_findings


# Engines whose verify*/verify_context return OK by construction
# (passive_gate proper + the aliases registry.py resolves to it). A
# rule routed through one of these never produces a finding via the
# audit dispatch, so excluding it from the firing-coverage gate is
# correct — its enforcement (if any) lives outside the audit pipeline
# at decoration time, registration time, or runtime.
_PASSIVE_ENGINE_IDS = frozenset(
    {
        "passive_gate",
        "python_runtime",
        "type_system",
        "runtime_metric",
        "advisory",
        "runtime_check",
        "dataclass_validation",
    }
)


# ID: 5b8a1c2d-9e3f-4a7b-8c5d-2e9f1a3b4c5d
def _check_per_file_scope_coverage(
    context: AuditorContext,
    executable_rules: list[Any],
) -> list[AuditFinding]:
    """Standing firing-coverage gate (ADR-076 D6).

    For every active enforcing per-file rule, verify the rule's scope
    matches at least one file in the walked set (same matcher dispatch
    uses). A zero-match enforcing rule is the #480 silent-inert class:
    it cannot fire and therefore cannot enforce its constraint.

    Exclusions:
      - Context-level rules (engine.verify_context, not file-iterated)
      - Empty-scope rules (scope: [], ADR-043 D7 deliberate)
      - Passive engines (route to passive_gate by construction)
      - Non-blocking rules (declared advisory/reporting/info — zero
        findings is consistent with intent)
    """
    findings: list[AuditFinding] = []
    for rule in executable_rules:
        if rule.is_context_level:
            continue
        if rule.engine in _PASSIVE_ENGINE_IDS:
            continue
        if not rule.scope:
            continue
        # Only enforcing rules need a non-empty walked-set; advisory/
        # reporting rules can have empty matches by intent.
        if rule.enforcement != "blocking":
            continue
        matched = context.get_files(include=rule.scope, exclude=rule.exclusions or [])
        if matched:
            continue
        findings.append(
            AuditFinding(
                check_id=f"{rule.rule_id}.scope_inert",
                severity=AuditSeverity.BLOCK,
                message=(
                    f"SCOPE_INERT: rule '{rule.rule_id}' is declared blocking "
                    f"but its scope matches zero files in the walked set. The "
                    f"rule cannot fire — its constraint is unenforceable in "
                    f"the current repo state. Either fix the scope "
                    f"({rule.scope}) or, if the rule is intentionally inert, "
                    f"declare it advisory/reporting in the policy document."
                ),
                file_path=None,
                context={
                    "finding_type": "SCOPE_INERT",
                    "engine": rule.engine,
                    "policy_id": rule.policy_id,
                    "scope": list(rule.scope),
                    "exclusions": list(rule.exclusions or []),
                },
            )
        )
    if findings:
        logger.warning(
            "SCOPE_INERT: %d enforcing per-file rule(s) match zero files: %s",
            len(findings),
            sorted(f.check_id for f in findings),
        )
    return findings


def _count_total_declared_rules(policies: dict[str, Any]) -> tuple[int, list[str]]:
    """Count ALL rules declared in constitutional policies.

    Returns the total count and list of all rule IDs, regardless of
    whether they have enforcement mappings. This is the true denominator
    for constitutional coverage.

    Returns:
        Tuple of (total_count, list_of_all_rule_ids).
    """
    all_rule_ids: list[str] = []
    for policy_data in policies.values():
        if not isinstance(policy_data, dict):
            continue
        rules = policy_data.get("rules", [])
        if not isinstance(rules, list):
            continue
        for rule_data in rules:
            if isinstance(rule_data, dict):
                rule_id = rule_data.get("id")
                if rule_id and isinstance(rule_id, str):
                    all_rule_ids.append(rule_id)
    return len(all_rule_ids), all_rule_ids


def _find_unmapped_rule_ids(
    policies: dict[str, Any],
    executable_rule_ids: set[str],
) -> list[str]:
    """Identify rules declared in the Constitution but not mapped to enforcement.

    These are laws that exist but cannot be checked — worse than having
    no law, because they create false confidence.
    """
    _, all_rule_ids = _count_total_declared_rules(policies)
    return sorted(set(all_rule_ids) - executable_rule_ids)


# ID: 692b645e-7aee-4811-9e3a-5fa51da2c159
def get_dynamic_execution_stats(
    context: AuditorContext,
    executed_rule_ids: set[str],
    crashed_rule_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Calculate comprehensive audit execution statistics.

    HARDENING P0.2: Stats now include the TRUE denominator (all declared
    rules), not just the mapped subset. Unmapped and crashed rules are
    explicitly enumerated so coverage numbers reflect reality.
    """
    if crashed_rule_ids is None:
        crashed_rule_ids = set()

    try:
        executable_rules = extract_executable_rules(
            context.policies, context.enforcement_loader
        )
        executable_rule_ids = {r.rule_id for r in executable_rules}

        # TRUE denominator: all rules declared in the Constitution
        total_declared, _ = _count_total_declared_rules(context.policies)

        # Rules that exist in law but have no enforcement mapping
        unmapped_rule_ids = _find_unmapped_rule_ids(
            context.policies, executable_rule_ids
        )

        # Rules that were mapped and executed successfully (no crash)
        cleanly_executed = executed_rule_ids - crashed_rule_ids

        # Coverage against the TRUE denominator
        effective_coverage = round(
            (len(cleanly_executed) / total_declared * 100) if total_declared else 0
        )

        # Coverage against mapped rules only (for comparison)
        mapped_coverage = round(
            (len(cleanly_executed) / len(executable_rules) * 100)
            if executable_rules
            else 0
        )

        # ADR-076 D4: effective dispatch mode is engine-derived per
        # check_type. Surface it here so the governor can see which
        # rules ran context-level vs per-file without reading src/.
        context_level_rule_ids = sorted(
            r.rule_id for r in executable_rules if r.is_context_level
        )
        per_file_rule_ids = sorted(
            r.rule_id for r in executable_rules if not r.is_context_level
        )

        return {
            # True denominator
            "total_declared_rules": total_declared,
            # Enforcement pipeline breakdown
            "total_executable_rules": len(executable_rules),
            "unmapped_rules": len(unmapped_rule_ids),
            "unmapped_rule_ids": unmapped_rule_ids,
            # Execution results
            "executed_dynamic_rules": len(executed_rule_ids),
            "cleanly_executed_rules": len(cleanly_executed),
            "crashed_rules": len(crashed_rule_ids),
            "crashed_rule_ids": sorted(crashed_rule_ids),
            # ADR-076 D4: effective dispatch mode per rule
            "context_level_rules": len(context_level_rule_ids),
            "context_level_rule_ids": context_level_rule_ids,
            "per_file_rules": len(per_file_rule_ids),
            "per_file_rule_ids": per_file_rule_ids,
            # Coverage (honest)
            "effective_coverage_percent": effective_coverage,
            "mapped_coverage_percent": mapped_coverage,
            # Existing callers read this key
            "coverage_percent": mapped_coverage,
        }
    except Exception as e:
        logger.error("Failed to calculate execution stats: %s", e)
        return {
            "total_declared_rules": 0,
            "total_executable_rules": 0,
            "unmapped_rules": 0,
            "unmapped_rule_ids": [],
            "executed_dynamic_rules": 0,
            "cleanly_executed_rules": 0,
            "crashed_rules": 0,
            "crashed_rule_ids": [],
            "context_level_rules": 0,
            "context_level_rule_ids": [],
            "per_file_rules": 0,
            "per_file_rule_ids": [],
            "effective_coverage_percent": 0,
            "mapped_coverage_percent": 0,
            "coverage_percent": 0,
            "stats_error": str(e),
        }
