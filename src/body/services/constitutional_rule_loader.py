# src/body/services/constitutional_rule_loader.py

"""
Constitutional rule loader — Mind-to-indices translation.

Reads governance rules from the Mind layer (.intent/rules/) via
IntentRepository and translates them into the queryable in-memory
indices that ConstitutionalValidator uses to answer governance queries.

This module owns the rule vocabulary: which statement patterns mean
"prohibited", which enforcement+authority combinations mean CRITICAL vs
ELEVATED, how scopes resolve to path patterns. When the .intent/ rule
vocabulary changes (a new enforcement level, a new statement pattern, a
new scope shape), this is the module that changes.

The validator (constitutional_validator.py) consumes the result via a
lazy import — see _populate_indices in that file — to avoid a circular
dependency on RiskTier, which is declared in the validator module.

LAYER: body/services — pure read-only translation. No filesystem writes,
no DB access. Returns a fresh _GovernanceIndices on each call; never
mutates external state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from body.services.constitutional_validator import RiskTier
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
class _GovernanceIndices:
    """Bundle of the six queryable indices produced from a load pass.

    Private (underscore-prefixed) because this shape only crosses the
    boundary between this loader and ConstitutionalValidator. Not a
    public API for callers.
    """

    rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    critical_paths: set[str] = field(default_factory=set)
    autonomous_actions: set[str] = field(default_factory=set)
    prohibited_actions: set[str] = field(default_factory=set)
    risk_by_path: dict[str, RiskTier] = field(default_factory=dict)
    risk_by_action: dict[str, RiskTier] = field(default_factory=dict)


# ID: 12bf933d-b3ee-4ef4-9e47-282db71af667
def load_governance_indices(intent_repo: Any) -> _GovernanceIndices:
    """Load .intent/ rules via IntentRepository and translate to indices.

    Args:
        intent_repo: An IntentRepository instance. The caller is
            responsible for instantiation; this function calls
            intent_repo.initialize() to ensure the rule index is built.

    Returns:
        A fresh _GovernanceIndices with the six populated collections.
        On an empty rule index, returns an _GovernanceIndices with all
        collections empty (no exception).
    """
    logger.info("📜 Loading constitutional governance rules...")

    intent_repo.initialize()
    indices = _GovernanceIndices()

    if not intent_repo._rule_index:
        logger.warning("No rules indexed in IntentRepository")
        return indices

    for rule_id, rule_ref in intent_repo._rule_index.items():
        try:
            # RuleRef has: rule_id, policy_id, source_path, content
            rule = rule_ref.content
            indices.rules[rule_id] = rule
            _process_rule(rule_id, rule, indices)
        except Exception as e:
            logger.warning("Failed to load rule %s: %s", rule_id, e)
            continue

    logger.info("✅ Loaded %s constitutional rules", len(indices.rules))
    logger.info("   📊 Critical paths: %s", len(indices.critical_paths))
    logger.info("   📊 Autonomous actions: %s", len(indices.autonomous_actions))
    logger.info("   📊 Prohibited actions: %s", len(indices.prohibited_actions))
    logger.info("   📊 Path risk mappings: %s", len(indices.risk_by_path))
    logger.info("   📊 Action risk mappings: %s", len(indices.risk_by_action))

    return indices


def _process_rule(
    rule_id: str, rule: dict[str, Any], indices: _GovernanceIndices
) -> None:
    """Extract governance information from one rule and update indices in-place."""
    statement = rule.get("statement", "")
    enforcement = rule.get("enforcement", "advisory")

    # Extract critical paths (blocking enforcement on .intent/)
    if ".intent" in statement and enforcement == "blocking":
        indices.critical_paths.add(".intent/**")

    # Extract autonomous permissions based on rule statements
    if "MUST NOT" in statement or "forbidden" in statement.lower():
        # Extract prohibited actions from rule statement
        if "eval" in statement or "exec" in statement:
            indices.prohibited_actions.add("execute_code")
        if "database" in statement.lower() and "Mind" in statement:
            indices.prohibited_actions.add("database_access_from_mind")

    # Classify risk based on enforcement strength and authority
    authority = rule.get("authority", "policy")
    if enforcement == "blocking" and authority == "constitution":
        # Constitutional blocking rules are CRITICAL
        if "path" in rule or "scope" in rule:
            scope = rule.get("scope", [])
            if isinstance(scope, dict):
                scope = scope.get("applies_to", [])
            for pattern in scope if isinstance(scope, list) else [scope]:
                if pattern:
                    indices.risk_by_path[pattern] = RiskTier.CRITICAL
    elif enforcement == "blocking":
        # Regular blocking rules are ELEVATED
        scope = rule.get("scope", [])
        if isinstance(scope, dict):
            scope = scope.get("applies_to", [])
        for pattern in scope if isinstance(scope, list) else [scope]:
            if pattern:
                indices.risk_by_path[pattern] = RiskTier.ELEVATED

    # Actions mentioned in advisory rules are ROUTINE if allowed
    if enforcement == "advisory" and "MAY" in statement:
        # Extract action name from rule_id or statement
        if "." in rule_id:
            action = rule_id.split(".")[-1]
            indices.autonomous_actions.add(action)
