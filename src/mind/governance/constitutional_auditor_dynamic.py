# src/mind/governance/constitutional_auditor_dynamic.py
"""
Dynamic Rule Execution Integration for ConstitutionalAuditor.

This module extends the existing ConstitutionalAuditor to execute rules directly
from policy JSON without requiring Python Check classes.

Integration approach:
1. Keep existing Check class discovery/execution (backward compatible)
2. Add dynamic rule extraction from policies
3. Execute both systems in parallel
4. Merge results

This is Phase 1 POC - runs alongside legacy system to prove the concept.

Ref: Dynamic Rule Execution Architecture
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: b8f3e9d7-6c2a-5e4f-9d8c-7b6a3e5f2c1d
async def run_dynamic_rules(
    context: AuditorContext, *, executed_rule_ids: set[str]
) -> list:
    """
    Execute all rules extracted from policies via their declared engines.

    This is the core dynamic rule execution function that:
    1. Extracts ExecutableRules from loaded policies
    2. Executes each rule via its engine
    3. Tracks which rules were executed
    4. Returns findings in AuditFinding format

    Args:
        context: AuditorContext with loaded policies and repo access
        executed_rule_ids: Set to update with executed rule IDs (for coverage tracking)

    Returns:
        List of AuditFinding objects from all dynamic rules

    Example flow:
        policies = context.policies  # Already loaded by AuditorContext
        rules = extract_executable_rules(policies)  # Convert to ExecutableRule instances
        for rule in rules:
            findings = await execute_rule(rule, context)  # Execute via engine

    Phase 1 POC Scope:
    - Execute all rules with engines defined
    - Log statistics for analysis
    - Don't modify legacy Check execution
    """
    all_findings = []

    # Extract executable rules from loaded policies
    try:
        executable_rules = extract_executable_rules(context.policies)
        logger.info(
            "Dynamic Rule Execution: Extracted %d executable rules from policies",
            len(executable_rules),
        )
    except Exception as e:
        logger.error("Failed to extract executable rules: %s", e, exc_info=True)
        return all_findings

    # Group by engine for statistics
    by_engine: dict[str, int] = {}
    for rule in executable_rules:
        by_engine[rule.engine] = by_engine.get(rule.engine, 0) + 1
    logger.info("Dynamic Rule Execution: Rules by engine: %s", by_engine)

    # Execute each rule
    executed_count = 0
    failed_count = 0

    for rule in executable_rules:
        try:
            # Track execution
            executed_rule_ids.add(rule.rule_id)
            executed_count += 1

            # Execute
            findings = await execute_rule(rule, context)
            all_findings.extend(findings)

            if findings:
                logger.debug(
                    "Dynamic Rule Execution: Rule %s found %d violations",
                    rule.rule_id,
                    len(findings),
                )
        except Exception as e:
            failed_count += 1
            logger.error(
                "Dynamic Rule Execution: Failed to execute rule %s: %s",
                rule.rule_id,
                e,
                exc_info=True,
            )
            # Don't stop - continue with other rules
            continue

    logger.info(
        "Dynamic Rule Execution: Completed %d/%d rules (%d failed, %d findings)",
        executed_count,
        len(executable_rules),
        failed_count,
        len(all_findings),
    )

    return all_findings


# ID: c9f4e8d7-5b3a-6e2f-8d9c-7b6a4e3f1c2d
def get_dynamic_execution_stats(
    context: AuditorContext, executed_rule_ids: set[str]
) -> dict[str, int]:
    """
    Calculate statistics about dynamic rule execution for reporting.

    Args:
        context: AuditorContext with loaded policies
        executed_rule_ids: Set of rule IDs that were executed

    Returns:
        Dictionary with execution statistics

    Example output:
        {
            "total_executable_rules": 45,
            "executed_dynamic_rules": 20,
            "coverage_percent": 44.4
        }
    """
    try:
        executable_rules = extract_executable_rules(context.policies)
        dynamic_executed = len(
            [r for r in executable_rules if r.rule_id in executed_rule_ids]
        )

        return {
            "total_executable_rules": len(executable_rules),
            "executed_dynamic_rules": dynamic_executed,
            "coverage_percent": round(
                (
                    (dynamic_executed / len(executable_rules) * 100)
                    if executable_rules
                    else 0.0
                ),
                1,
            ),
        }
    except Exception as e:
        logger.error("Failed to calculate dynamic execution stats: %s", e)
        return {
            "total_executable_rules": 0,
            "executed_dynamic_rules": 0,
            "coverage_percent": 0.0,
        }
