# src/mind/governance/filtered_audit.py
"""
Filtered Constitutional Audit - Run specific rules or policies.

Enables focused remediation by allowing execution of:
- Single rules: --rule linkage.capability.unassigned
- Single policies: --policy standard_code_linkage
- Multiple rules: --rule rule1 --rule rule2
- Rule patterns: --rule-pattern "linkage.*"

This uses the existing dynamic rule execution engine but with filtering.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)


# ID: f8a9b7c6-5d4e-3f2a-1b0c-9d8e7f6a5b4c
class RuleFilter:
    """Filters rules based on user-specified criteria."""

    def __init__(
        self,
        rule_ids: list[str] | None = None,
        policy_ids: list[str] | None = None,
        rule_patterns: list[str] | None = None,
    ):
        self.rule_ids = set(rule_ids or [])
        self.policy_ids = set(policy_ids or [])
        self.rule_patterns = [re.compile(p) for p in (rule_patterns or [])]

    # ID: ee2ebac1-0f32-45ce-ab11-ed0c4106ab20
    def matches(self, rule: ExecutableRule) -> bool:
        """Check if rule matches filter criteria."""
        # If no filters specified, match everything
        if not self.rule_ids and not self.policy_ids and not self.rule_patterns:
            return True

        # Check exact rule ID match
        if self.rule_ids and rule.rule_id in self.rule_ids:
            return True

        # Check policy ID match
        if self.policy_ids and rule.policy_id in self.policy_ids:
            return True

        # Check pattern match
        for pattern in self.rule_patterns:
            if pattern.match(rule.rule_id):
                return True

        return False


# ID: a7b8c9d0-1e2f-3g4h-5i6j-7k8l9m0n1o2p
# ID: 24e155df-a90f-4c36-825f-4446c4f3a142
async def run_filtered_audit(
    context: AuditorContext,
    *,
    rule_ids: list[str] | None = None,
    policy_ids: list[str] | None = None,
    rule_patterns: list[str] | None = None,
    executed_rule_ids: set[str] | None = None,
) -> tuple[list, set[str], dict[str, int]]:
    """
    Execute filtered subset of constitutional rules.

    Args:
        context: AuditorContext with repo and policy info
        rule_ids: Specific rule IDs to execute
        policy_ids: Execute all rules from these policies
        rule_patterns: Regex patterns for rule IDs
        executed_rule_ids: Set to track executed rules (optional)

    Returns:
        tuple(findings, executed_rules, stats)
        - findings: List of AuditFinding dicts
        - executed_rules: Set of rule IDs that were executed
        - stats: Dict with execution statistics
    """
    if executed_rule_ids is None:
        executed_rule_ids = set()

    # Extract all executable rules from policies
    all_rules = extract_executable_rules(context.policies)

    # Create filter
    rule_filter = RuleFilter(
        rule_ids=rule_ids,
        policy_ids=policy_ids,
        rule_patterns=rule_patterns,
    )

    # Filter rules
    filtered_rules = [r for r in all_rules if rule_filter.matches(r)]

    if not filtered_rules:
        logger.warning(
            "No rules matched filter criteria: rule_ids=%s, policy_ids=%s, patterns=%s",
            rule_ids,
            policy_ids,
            rule_patterns,
        )
        return (
            [],
            executed_rule_ids,
            {
                "total_rules": len(all_rules),
                "filtered_rules": 0,
                "executed_rules": 0,
                "total_findings": 0,
            },
        )

    logger.info(
        "Filtered audit: %d rules selected (out of %d total)",
        len(filtered_rules),
        len(all_rules),
    )

    # Execute filtered rules
    all_findings = []
    failed_rules = []

    for rule in filtered_rules:
        try:
            findings = await execute_rule(rule, context)
            all_findings.extend([f.as_dict() for f in findings])
            executed_rule_ids.add(rule.rule_id)

            logger.debug(
                "Rule %s: %d findings",
                rule.rule_id,
                len(findings),
            )
        except Exception as e:
            logger.error(
                "Rule %s execution failed: %s",
                rule.rule_id,
                e,
                exc_info=True,
            )
            failed_rules.append(rule.rule_id)

    stats = {
        "total_rules": len(all_rules),
        "filtered_rules": len(filtered_rules),
        "executed_rules": len(executed_rule_ids),
        "failed_rules": len(failed_rules),
        "total_findings": len(all_findings),
    }

    logger.info(
        "Filtered audit complete: %d/%d rules executed, %d findings",
        stats["executed_rules"],
        stats["filtered_rules"],
        stats["total_findings"],
    )

    if failed_rules:
        logger.warning("Failed rules: %s", ", ".join(failed_rules))

    return all_findings, executed_rule_ids, stats
