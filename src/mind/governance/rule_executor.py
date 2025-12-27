# src/mind/governance/rule_executor.py
"""
Rule Executor - Executes ExecutableRules via the engine registry.

This module takes an ExecutableRule and executes it against the codebase:
1. Gets the appropriate engine from EngineRegistry
2. For context-level engines: calls verify_context()
3. For file-level engines: gets files and calls verify() on each
4. Converts violations to AuditFindings

Design:
- Pure orchestration (connects existing pieces)
- Engine does actual verification
- Returns standard AuditFinding objects

Ref: Dynamic Rule Execution Architecture
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mind.governance.executable_rule import ExecutableRule
from mind.logic.engines.registry import EngineRegistry
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: a9f7e2d8-6c3b-5e4f-8d9c-7b6a4e3f1c2d
async def execute_rule(
    rule: ExecutableRule, context: AuditorContext
) -> list[AuditFinding]:
    """
    Execute a single ExecutableRule via its engine.

    Flow:
    1. Get engine from registry
    2. Check if engine is context-level (knowledge_gate, workflow_gate)
    3a. If context-level: call verify_context(context, params) once
    3b. If file-level: get files and call verify(file, params) on each
    4. Convert violations to AuditFindings

    Args:
        rule: ExecutableRule to execute
        context: AuditorContext with repo info and file access

    Returns:
        List of AuditFinding instances (empty if no violations)

    Example:
        rule = ExecutableRule(
            rule_id="async.runtime.no_nested_loop_creation",
            engine="ast_gate",
            params={"check_type": "restrict_event_loop_creation"},
            enforcement="error"
        )
        findings = await execute_rule(rule, context)
    """
    findings: list[AuditFinding] = []

    # Get engine
    try:
        engine = EngineRegistry.get(rule.engine)
    except ValueError as e:
        logger.error(
            "Failed to get engine '%s' for rule %s: %s", rule.engine, rule.rule_id, e
        )
        # Return a finding about the configuration error
        findings.append(
            AuditFinding(
                check_id=f"{rule.rule_id}.engine_missing",
                severity=AuditSeverity.ERROR,
                message=f"Rule '{rule.rule_id}' requires engine '{rule.engine}' which is not available: {e}",
                file_path="N/A",
            )
        )
        return findings

    # CONTEXT-LEVEL ENGINES (knowledge_gate, workflow_gate)
    # These engines operate on the full AuditorContext, not individual files
    if rule.is_context_level:
        logger.debug(
            "Rule %s: executing context-level engine '%s'",
            rule.rule_id,
            rule.engine,
        )

        try:
            # Call the context-aware verify method
            if hasattr(engine, "verify_context"):
                findings_from_engine = engine.verify_context(context, rule.params)
                findings.extend(findings_from_engine)
            else:
                logger.error(
                    "Engine '%s' is marked as context-level but doesn't have verify_context() method",
                    rule.engine,
                )
                findings.append(
                    AuditFinding(
                        check_id=f"{rule.rule_id}.engine_error",
                        severity=AuditSeverity.ERROR,
                        message=f"Context-level engine '{rule.engine}' missing verify_context() method",
                        file_path="N/A",
                    )
                )
        except Exception as e:
            logger.error(
                "Context-level engine '%s' failed for rule %s: %s",
                rule.engine,
                rule.rule_id,
                e,
                exc_info=True,
            )
            findings.append(
                AuditFinding(
                    check_id=f"{rule.rule_id}.execution_error",
                    severity=AuditSeverity.ERROR,
                    message=f"Rule '{rule.rule_id}' execution failed: {e}",
                    file_path="N/A",
                )
            )

        if findings:
            logger.debug("Rule %s: found %d violations", rule.rule_id, len(findings))

        return findings

    # FILE-LEVEL ENGINES (ast_gate, glob_gate, regex_gate, llm_gate)
    # These engines operate on individual files
    logger.debug(
        "Rule %s: executing file-level engine '%s'",
        rule.rule_id,
        rule.engine,
    )

    # Get files to check
    try:
        files = context.get_files(include=rule.scope, exclude=rule.exclusions)
        logger.debug(
            "Rule %s: checking %d files (scope=%s, exclusions=%s)",
            rule.rule_id,
            len(files),
            rule.scope,
            rule.exclusions,
        )
    except Exception as e:
        logger.error("Failed to get files for rule %s: %s", rule.rule_id, e)
        findings.append(
            AuditFinding(
                check_id=f"{rule.rule_id}.scope_error",
                severity=AuditSeverity.ERROR,
                message=f"Rule '{rule.rule_id}' failed to resolve file scope: {e}",
                file_path="N/A",
            )
        )
        return findings

    # Execute engine on each file
    for file_path in files:
        try:
            result = engine.verify(file_path, rule.params)

            if not result.ok:
                # Convert engine violations to AuditFindings
                for violation_msg in result.violations:
                    findings.append(
                        AuditFinding(
                            check_id=rule.rule_id,
                            severity=(
                                AuditSeverity.ERROR
                                if rule.enforcement == "error"
                                else AuditSeverity.WARNING
                            ),
                            message=violation_msg,
                            file_path=str(file_path.relative_to(context.repo_path)),
                        )
                    )
        except Exception as e:
            logger.warning(
                "Engine '%s' failed on file %s for rule %s: %s",
                rule.engine,
                file_path.name,
                rule.rule_id,
                e,
            )
            # Don't add finding for individual file failures - they might be legitimate parse errors
            # that other checks will catch
            continue

    if findings:
        logger.debug("Rule %s: found %d violations", rule.rule_id, len(findings))

    return findings
