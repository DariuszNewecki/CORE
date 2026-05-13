# src/mind/governance/rule_extractor.py

"""
Rule Extractor - Combines Constitutional Law with Enforcement Mappings

This module implements the derivation boundary:
    Constitution (5 canonical fields) → Enforcement Mappings → ExecutableRules

CONSTITUTIONAL ALIGNMENT:
- Rules contain ONLY the 5 canonical fields
- Enforcement strategies are derived artifacts
- Missing mappings = declared but not implementable (safe degradation)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.enforcement_loader import EnforcementMappingLoader
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)


# Context-level engines (operate on full AuditorContext, not individual files)
CONTEXT_LEVEL_ENGINES = frozenset({"workflow_gate", "knowledge_gate"})


# ID: bb50b995-53a3-436d-bd01-10f6ab0c8a42
def extract_executable_rules(
    policies: dict[str, dict[str, Any]], enforcement_loader: EnforcementMappingLoader
) -> list[ExecutableRule]:
    """
    Combines canonical rules (law) with enforcement mappings (implementation).

    This is where derivation happens: Constitution → Executable Artifacts

    Args:
        policies: Dictionary of policy_id -> policy data from AuditorContext
        enforcement_loader: Loader for enforcement mappings

    Returns:
        List of ExecutableRule instances ready for dynamic execution

    Design:
        1. Extract canonical rules from policies (5 fields only)
        2. Look up enforcement mapping for each rule
        3. Combine into ExecutableRule
        4. Log rules without mappings (declared but not implementable)
    """
    from mind.governance.executable_rule import ExecutableRule

    executable_rules: list[ExecutableRule] = []
    declared_only_rules: list[str] = []

    for policy_id, policy_data in policies.items():
        if not isinstance(policy_data, dict):
            logger.debug("Skipping non-dict policy: %s", policy_id)
            continue

        rules = policy_data.get("rules", [])
        if not isinstance(rules, list):
            logger.debug("Policy %s has no rules list", policy_id)
            continue

        for rule_data in rules:
            if not isinstance(rule_data, dict):
                continue

            # Extract rule ID
            rule_id = rule_data.get("id")
            if not rule_id or not isinstance(rule_id, str):
                logger.warning(
                    "Skipping rule in policy %s: missing or invalid id", policy_id
                )
                continue

            # CONSTITUTIONAL LAW: Extract only the 5 canonical fields
            canonical_rule = {
                "id": rule_data.get("id"),
                "statement": rule_data.get("statement", ""),
                "enforcement": rule_data.get("enforcement", "reporting"),
                "authority": rule_data.get("authority", "policy"),
                "phase": rule_data.get("phase", "audit"),
            }

            # Validate canonical fields
            if not all(canonical_rule.values()):
                logger.warning(
                    "Rule %s missing required canonical fields: %s",
                    rule_id,
                    [k for k, v in canonical_rule.items() if not v],
                )
                continue

            # DERIVED ARTIFACT: Get enforcement strategy
            strategy = enforcement_loader.get_enforcement_strategy(rule_id)

            if not strategy:
                # Rule exists but has no implementation mapping
                declared_only_rules.append(rule_id)
                logger.debug(
                    "Rule %s declared but not implementable (no enforcement mapping)",
                    rule_id,
                )
                continue

            # Validate enforcement strategy has required fields
            engine = strategy.get("engine")
            if not engine:
                logger.warning(
                    "Enforcement mapping for %s missing engine field", rule_id
                )
                continue

            # Extract scope from enforcement mapping
            scope_data = strategy.get("scope", {})
            if isinstance(scope_data, dict):
                if "applies_to" not in scope_data:
                    logger.warning(
                        "Rule %s scope is missing 'applies_to' — rule will match "
                        "nothing rather than silently widen to all of src/ (#158)",
                        rule_id,
                    )
                scope = scope_data.get("applies_to", [])
                exclusions = scope_data.get("excludes", [])
            else:
                # Non-dict scope_data is malformed — match nothing instead of
                # widening repo-wide (#158).
                logger.warning(
                    "Rule %s has non-dict scope %r — rule will match nothing "
                    "rather than silently widen to all of src/ (#158)",
                    rule_id,
                    type(scope_data).__name__,
                )
                scope = []
                exclusions = []

            # Ensure scope and exclusions are lists
            if isinstance(scope, str):
                scope = [scope]
            if isinstance(exclusions, str):
                exclusions = [exclusions]

            # ADR-042 D3: merge governed_exclusions[].file into the exclusion
            # list. The governed_exclusions block is a structured register
            # carrying rationale + category + removal_condition for each
            # exemption; the audit pipeline honors it by treating the listed
            # files as if they were in scope.excludes. Per-entry shape is
            # enforced by enforcement_mapping.schema.json; rule_extractor is
            # defensive against malformed entries (skip, log) rather than
            # raising — the schema validator is the canonical gate.
            governed = strategy.get("governed_exclusions", []) or []
            if isinstance(governed, list):
                for entry in governed:
                    if not isinstance(entry, dict):
                        logger.warning(
                            "Rule %s governed_exclusions entry is not a dict: %r",
                            rule_id,
                            entry,
                        )
                        continue
                    path = entry.get("file")
                    if not path:
                        logger.warning(
                            "Rule %s governed_exclusions entry missing 'file': %r",
                            rule_id,
                            entry,
                        )
                        continue
                    exclusions.append(path)

            # Determine if this is a context-level engine
            is_context_level = engine in CONTEXT_LEVEL_ENGINES

            # ADR-043 D2: pre-selector dependency list. Parsed defensively
            # here; canonical type/shape is enforced by
            # enforcement_mapping.schema.json. Topological ordering and
            # cross-rule reference validation happen after the loop, once
            # the full rule set is known.
            requires_findings_from_raw = (
                strategy.get("requires_findings_from", []) or []
            )
            requires_findings_from: list[str] = []
            if isinstance(requires_findings_from_raw, list):
                for entry in requires_findings_from_raw:
                    if isinstance(entry, str) and entry:
                        requires_findings_from.append(entry)
                    else:
                        logger.warning(
                            "Rule %s requires_findings_from entry malformed "
                            "(not a non-empty string): %r — ignoring",
                            rule_id,
                            entry,
                        )
            else:
                logger.warning(
                    "Rule %s requires_findings_from is not a list (got %s) — ignoring",
                    rule_id,
                    type(requires_findings_from_raw).__name__,
                )

            if requires_findings_from and is_context_level:
                logger.error(
                    "Rule %s has requires_findings_from but engine %s is "
                    "context-level — context-level rules cannot use a "
                    "per-file pre-selector. Clearing requires_findings_from.",
                    rule_id,
                    engine,
                )
                requires_findings_from = []

            # Build executable rule from law + implementation.
            # authority is threaded from the canonical rule so IntentGuard
            # can distinguish "always-block" (constitution) from "advisory"
            # (policy) without a global strict_mode override.
            executable_rule = ExecutableRule(
                rule_id=rule_id,
                engine=engine,
                params=strategy.get("params", {}),
                enforcement=canonical_rule["enforcement"],
                statement=canonical_rule["statement"],
                scope=scope,
                exclusions=exclusions,
                policy_id=policy_id,
                is_context_level=is_context_level,
                authority=canonical_rule["authority"],
                requires_findings_from=requires_findings_from,
            )

            executable_rules.append(executable_rule)

            logger.debug(
                "Extracted rule: %s (engine=%s, authority=%s, context_level=%s, scope=%d patterns)",
                rule_id,
                engine,
                canonical_rule["authority"],
                is_context_level,
                len(scope),
            )

    # Report statistics
    logger.info(
        "Extracted %d executable rules from %d policies",
        len(executable_rules),
        len(policies),
    )

    if declared_only_rules:
        logger.info(
            "Found %d declared-only rules (no enforcement mappings): %s",
            len(declared_only_rules),
            ", ".join(declared_only_rules[:5])
            + ("..." if len(declared_only_rules) > 5 else ""),
        )

    return _topologically_sort_rules(executable_rules)


def _topologically_sort_rules(
    rules: list[ExecutableRule],
) -> list[ExecutableRule]:
    """
    Order rules so each rule appears after its requires_findings_from
    preconditions (ADR-043 D2). Original extraction order is preserved
    among rules with no edges between them — when no rule uses
    requires_findings_from, this is a no-op.

    References to rules that do not exist in the input set are dropped
    with a logged warning. Cycles are detected, logged at ERROR, and
    broken by clearing requires_findings_from on the cycle members so
    they fall back to their original position without producing empty
    intersections at runtime.
    """
    if not rules:
        return rules

    position: dict[str, int] = {r.rule_id: i for i, r in enumerate(rules)}
    by_id: dict[str, ExecutableRule] = {r.rule_id: r for r in rules}

    # Resolve references against the actual rule set. Unknown references
    # are dropped (with a warning) so they cannot inject phantom edges.
    in_deps: dict[str, set[str]] = {}
    for r in rules:
        valid_preconditions: list[str] = []
        for pre in r.requires_findings_from:
            if pre in by_id:
                valid_preconditions.append(pre)
            else:
                logger.warning(
                    "Rule %s requires_findings_from references unknown rule "
                    "%s — ignoring this edge",
                    r.rule_id,
                    pre,
                )
        r.requires_findings_from = valid_preconditions
        in_deps[r.rule_id] = set(valid_preconditions)

    # Reverse adjacency for Kahn's algorithm.
    dependents: dict[str, list[str]] = {rid: [] for rid in by_id}
    for rid, preconditions in in_deps.items():
        for pre in preconditions:
            dependents[pre].append(rid)

    in_degree: dict[str, int] = {rid: len(in_deps[rid]) for rid in by_id}
    sorted_rules: list[ExecutableRule] = []
    ready: list[str] = [rid for rid in by_id if in_degree[rid] == 0]
    ready.sort(key=lambda rid: position[rid])

    while ready:
        rid = ready.pop(0)
        sorted_rules.append(by_id[rid])
        for dep_id in dependents[rid]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                ready.append(dep_id)
        ready.sort(key=lambda rid: position[rid])

    if len(sorted_rules) < len(rules):
        placed_ids = {r.rule_id for r in sorted_rules}
        cycle_members = [r for r in rules if r.rule_id not in placed_ids]
        logger.error(
            "Cycle detected in requires_findings_from graph among %d rules: "
            "%s. Clearing requires_findings_from on the cycle members and "
            "falling back to original extraction order for them — otherwise "
            "they would silently produce empty intersections at runtime.",
            len(cycle_members),
            [r.rule_id for r in cycle_members],
        )
        for r in cycle_members:
            r.requires_findings_from = []
            sorted_rules.append(r)

    return sorted_rules


__all__ = ["CONTEXT_LEVEL_ENGINES", "extract_executable_rules"]
