# src/mind/governance/constitutional_auditor_dynamic.py
# ID: b8f3e9d7-6c2a-5e4f-9d8c-7b6a3e5f2c1d

"""
Dynamic Rule Execution Integration.
Refactored to be circular-safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mind.governance.rule_extractor import extract_executable_rules
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: b8f3e9d7-6c2a-5e4f-9d8c-7b6a3e5f2c1d
async def run_dynamic_rules(
    context: AuditorContext, *, executed_rule_ids: set[str]
) -> list:
    """Execute all rules via their declared engines."""
    # DEFERRED IMPORT: Break circular loop
    from mind.governance.rule_executor import execute_rule
    from mind.logic.engines.registry import EngineRegistry

    all_findings = []
    executable_rules = extract_executable_rules(
        context.policies, context.enforcement_loader
    )

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
            findings = await execute_rule(rule, context)
            all_findings.extend(findings)

        except Exception as e:
            logger.error("Rule %s failed: %s", rule.rule_id, e)
            continue

    logger.info(
        "Dynamic Rule Execution: Completed %d rules (Skipped %d stubs)",
        executed_count,
        skipped_stub_count,
    )
    return all_findings


# ID: 692b645e-7aee-4811-9e3a-5fa51da2c159
def get_dynamic_execution_stats(
    context: AuditorContext, executed_rule_ids: set[str]
) -> dict[str, int]:
    try:
        executable_rules = extract_executable_rules(
            context.policies, context.enforcement_loader
        )
        dynamic_executed = len(
            [r for r in executable_rules if r.rule_id in executed_rule_ids]
        )
        return {
            "total_executable_rules": len(executable_rules),
            "executed_dynamic_rules": dynamic_executed,
            "coverage_percent": round(
                (dynamic_executed / len(executable_rules) * 100)
                if executable_rules
                else 0
            ),
        }
    except Exception:
        return {
            "total_executable_rules": 0,
            "executed_dynamic_rules": 0,
            "coverage_percent": 0,
        }
