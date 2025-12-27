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

# Engines that operate on full AuditorContext instead of individual files
CONTEXT_LEVEL_ENGINES = {"knowledge_gate", "workflow_gate"}


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
            logger.debug("Policy %s has no rules list", policy_id)
            continue

        for rule_data in rules:
            if not isinstance(rule_data, dict):
                continue

            # Extract check block
            check_block = rule_data.get("check", {})
            if not isinstance(check_block, dict):
                continue

            # Must have an engine defined
            engine_id = check_block.get("engine")
            if not engine_id or not isinstance(engine_id, str):
                continue

            # Extract rule components
            rule_id = rule_data.get("id", "")
            if not rule_id or not isinstance(rule_id, str):
                logger.warning(
                    "Skipping rule in policy %s: missing or invalid id", policy_id
                )
                continue

            params = check_block.get("params", {})
            if not isinstance(params, dict):
                params = {}

            enforcement = rule_data.get("enforcement", "error")
            if not isinstance(enforcement, str):
                enforcement = "error"

            statement = rule_data.get("statement", "")
            if not isinstance(statement, str):
                statement = ""

            # Extract scope/exclusions
            scope = rule_data.get("scope", ["src/**/*.py"])
            if isinstance(scope, str):
                scope = [scope]
            elif not isinstance(scope, list):
                scope = ["src/**/*.py"]

            exclusions = rule_data.get("exclusions", [])
            if isinstance(exclusions, str):
                exclusions = [exclusions]
            elif not isinstance(exclusions, list):
                exclusions = []

            # Determine if this is a context-level engine
            is_context_level = engine_id in CONTEXT_LEVEL_ENGINES

            # Create ExecutableRule
            executable_rule = ExecutableRule(
                rule_id=rule_id,
                engine=engine_id,
                params=params,
                enforcement=enforcement,
                statement=statement,
                scope=scope,
                exclusions=exclusions,
                policy_id=policy_id,
                is_context_level=is_context_level,
            )

            executable_rules.append(executable_rule)

            logger.debug(
                "Extracted rule: %s (engine=%s, context_level=%s)",
                rule_id,
                engine_id,
                is_context_level,
            )

    logger.info(
        "Extracted %d executable rules from %d policies",
        len(executable_rules),
        len(policies),
    )

    return executable_rules
