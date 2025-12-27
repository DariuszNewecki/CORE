# src/mind/governance/rule_extractor.py
"""
Rule Extraction - Converts policy JSON into ExecutableRule instances.

This module scans loaded policies and extracts rules that have engines assigned,
making them ready for dynamic execution without requiring Python Check classes.

Flow:
1. AuditorContext loads all policies from .intent/ into context.policies
2. extract_executable_rules() scans those policies
3. Returns list of ExecutableRule instances
4. Auditor executes them via EngineRegistry

Design:
- Pure data transformation (policies dict → ExecutableRule list)
- No I/O, no side effects
- Defensive parsing (skip malformed rules)

Ref: Dynamic Rule Execution Architecture
"""

from __future__ import annotations

from typing import Any

from mind.governance.executable_rule import ExecutableRule
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f8e3d9c7-5a2b-4e1f-9d8c-7b6a3e5f2c4d
def extract_executable_rules(policies: dict[str, Any]) -> list[ExecutableRule]:
    """
    Extract all executable rules from loaded policy dictionaries.

    Scans all policies for rules with "check.engine" defined and converts
    them into ExecutableRule instances ready for dynamic execution.

    Args:
        policies: Dictionary of policy_id -> policy_data from AuditorContext

    Returns:
        List of ExecutableRule instances

    Example policy structure:
        {
            "standard_architecture_dependency_injection": {
                "id": "standard_architecture_dependency_injection",
                "rules": [
                    {
                        "id": "async.runtime.no_nested_loop_creation",
                        "enforcement": "error",
                        "statement": "Code MUST NOT call asyncio.run()...",
                        "check": {
                            "engine": "ast_gate",
                            "params": {"check_type": "restrict_event_loop_creation"}
                        },
                        "scope": ["src/**/*.py"],
                        "exclusions": ["tests/**"]
                    }
                ]
            }
        }
    """
    executable_rules: list[ExecutableRule] = []

    for policy_id, policy_data in policies.items():
        if not isinstance(policy_data, dict):
            logger.debug("Skipping non-dict policy: %s", policy_id)
            continue

        rules = policy_data.get("rules", [])
        if not isinstance(rules, list):
            logger.debug("Policy %s has non-list rules, skipping", policy_id)
            continue

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            # Check if rule has engine assigned
            check_block = rule.get("check")
            if not isinstance(check_block, dict):
                continue

            engine = check_block.get("engine")
            if not engine or not isinstance(engine, str):
                continue

            # Extract rule data
            rule_id = rule.get("id")
            if not rule_id:
                logger.warning("Rule in policy %s missing 'id', skipping", policy_id)
                continue

            try:
                executable_rule = ExecutableRule(
                    rule_id=str(rule_id),
                    engine=str(engine),
                    params=check_block.get("params", {}),
                    enforcement=str(rule.get("enforcement", "error")),
                    statement=str(rule.get("statement", "")),
                    scope=rule.get("scope", ["src/**/*.py"]),
                    exclusions=rule.get("exclusions", []),
                    policy_id=str(policy_id),
                )
                executable_rules.append(executable_rule)
                logger.debug(
                    "Extracted rule: %s (engine=%s) from policy %s",
                    rule_id,
                    engine,
                    policy_id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to extract rule %s from policy %s: %s",
                    rule_id,
                    policy_id,
                    e,
                )
                continue

    logger.info(
        "Extracted %d executable rules from %d policies",
        len(executable_rules),
        len(policies),
    )

    return executable_rules
