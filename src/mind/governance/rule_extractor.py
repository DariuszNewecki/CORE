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
                scope = scope_data.get("applies_to", ["src/**/*.py"])
                exclusions = scope_data.get("excludes", [])
            else:
                # Fallback for simple scope definitions
                scope = ["src/**/*.py"]
                exclusions = []

            # Ensure scope and exclusions are lists
            if isinstance(scope, str):
                scope = [scope]
            if isinstance(exclusions, str):
                exclusions = [exclusions]

            # Determine if this is a context-level engine
            is_context_level = engine in CONTEXT_LEVEL_ENGINES

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
                authority=canonical_rule["authority"],  # NEW: thread authority through
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

    return executable_rules


__all__ = ["CONTEXT_LEVEL_ENGINES", "extract_executable_rules"]
