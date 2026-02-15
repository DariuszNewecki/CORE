# src/mind/governance/rule_conflict_detector.py

"""
Rule Conflict Detector - Constitutional Governance Validation

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Detect rule conflicts at load time
- Implements CORE-Rule-Conflict-Semantics.md
- No runtime enforcement logic

Per CORE-Rule-Conflict-Semantics.md:
- Conflicts between equal-authority rules are governance errors
- Must be resolved in .intent policies, not by runtime precedence
"""

from __future__ import annotations

from collections import defaultdict

from mind.governance.policy_rule import PolicyRule
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5de19f6c-26f7-4252-9f1a-7fa8fa41576c
# ID: 27a0babb-934b-48ef-bf4b-7eed998c4f1d
class RuleConflictDetector:
    """
    Detects conflicts between constitutional rules.

    Constitutional Compliance:
    - NO precedence-based conflict resolution
    - Equal-authority conflicts are governance errors
    - Enforces CORE-Rule-Conflict-Semantics.md
    """

    # ID: e3df65ae-5a64-40c5-b102-2ddcc3059027
    # ID: 225b2f42-fcd4-430f-8c73-760876d73c68
    @staticmethod
    # ID: 479c3822-cb01-4af4-86c6-2bd8743de061
    def detect_conflicts(rules: list[PolicyRule]) -> list[dict[str, str]]:
        """
        Detect conflicts between rules of equal authority.

        Per CORE-Rule-Conflict-Semantics.md Section 2:
        A rule conflict exists when:
        1. Two or more rules apply at the same Phase (pattern overlap)
        2. The rules have the same Authority level
        3. The rules produce incompatible outcomes

        Args:
            rules: List of policy rules to check

        Returns:
            List of conflict descriptions with rule names and details
        """
        conflicts = []

        # Group rules by pattern to find overlapping enforcement
        pattern_groups = defaultdict(list)
        for rule in rules:
            pattern_groups[rule.pattern].append(rule)

        # Check each pattern group for conflicts
        for pattern, pattern_rules in pattern_groups.items():
            if len(pattern_rules) < 2:
                continue

            # Check for incompatible actions among equal-authority rules
            for i, rule1 in enumerate(pattern_rules):
                for rule2 in pattern_rules[i + 1 :]:
                    # If both rules have same severity (proxy for authority level)
                    # and incompatible actions, that's a conflict
                    if rule1.severity == rule2.severity:
                        if RuleConflictDetector._actions_are_incompatible(
                            rule1.action, rule2.action
                        ):
                            conflicts.append(
                                {
                                    "rule1": rule1.name,
                                    "rule2": rule2.name,
                                    "pattern": pattern,
                                    "authority": rule1.severity,
                                    "action1": rule1.action,
                                    "action2": rule2.action,
                                }
                            )

        return conflicts

    # ID: 55a39d52-f85d-4b08-927d-b0689b0c8479
    # ID: c23b6a3a-65b9-4f97-925e-4130ac2078d0
    @staticmethod
    def _actions_are_incompatible(action1: str, action2: str) -> bool:
        """
        Determine if two rule actions are mutually incompatible.

        Incompatible actions:
        - "deny" vs "allow" (one forbids, one permits)
        - Different engine dispatch targets for same pattern

        Compatible actions (not conflicts):
        - "deny" and "deny" (redundant but not contradictory)
        - "warn" and "warn" (redundant reporting)
        - "warn" and "deny" (deny is stricter, no conflict)

        Args:
            action1: First rule action
            action2: Second rule action

        Returns:
            True if actions conflict
        """
        # Normalize actions
        a1, a2 = action1.lower(), action2.lower()

        # Explicit allow/deny conflict
        if {a1, a2} == {"deny", "allow"}:
            return True

        # Different engine dispatches on same pattern is a conflict
        if a1.startswith("engine:") and a2.startswith("engine:"):
            if a1 != a2:
                return True

        # warn + deny is NOT a conflict (deny is stricter)
        # deny + deny is NOT a conflict (redundant)
        # warn + warn is NOT a conflict

        return False
