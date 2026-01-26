# src/mind/governance/rule_executor.py
"""
Rule Executor - Executes constitutional rules via their declared engines.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Uses natively async engine dispatch to prevent loop hijacking.

CONSTITUTIONAL FIX:
- Context-level engines now respect rule enforcement levels (advisory/warning/blocking)
- Previously all workflow_gate violations showed as ERROR regardless of enforcement setting
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)


# ID: map_enforcement_to_severity
def _map_enforcement_to_severity(enforcement: str) -> AuditSeverity:
    """
    Map canonical enforcement values to AuditSeverity.
    """
    enforcement_lower = enforcement.lower()

    if enforcement_lower in ("blocking", "error"):
        return AuditSeverity.ERROR
    elif enforcement_lower in ("reporting", "warning"):
        return AuditSeverity.WARNING
    elif enforcement_lower == "advisory":
        return AuditSeverity.INFO
    else:
        logger.warning(
            "Unknown enforcement value '%s', defaulting to WARNING", enforcement
        )
        return AuditSeverity.WARNING


# ID: 5c8d9e7f-6a4b-3c2d-1e0f-9a8b7c6d5e4f
async def execute_rule(
    rule: ExecutableRule, context: AuditorContext
) -> list[AuditFinding]:
    """
    Execute a single ExecutableRule via its engine.

    Flow:
    1. Get engine from registry
    2. Check if engine is context-level
    3a. If context-level: call verify_context(context, params)
    3b. If file-level: get files and call verify(file, params)
    4. Convert violations to AuditFindings
    """
    from mind.logic.engines.registry import EngineRegistry

    findings: list[AuditFinding] = []

    # Get engine
    try:
        engine = EngineRegistry.get(rule.engine)
    except ValueError as e:
        logger.error(
            "Failed to get engine '%s' for rule %s: %s", rule.engine, rule.rule_id, e
        )
        findings.append(
            AuditFinding(
                check_id=f"{rule.rule_id}.engine_missing",
                severity=AuditSeverity.ERROR,
                message=f"Rule '{rule.rule_id}' requires engine '{rule.engine}' which is not available: {e}",
                file_path="none",
            )
        )
        return findings

    # CONTEXT-LEVEL ENGINES (knowledge_gate, workflow_gate)
    if rule.is_context_level:
        logger.debug(
            "Rule %s: executing context-level engine '%s'",
            rule.rule_id,
            rule.engine,
        )

        # CONSTITUTIONAL FIX: Map enforcement level to severity for context-level engines
        # This was missing - file-level engines got this mapping but context-level didn't
        severity = _map_enforcement_to_severity(rule.enforcement)

        try:
            if hasattr(engine, "verify_context"):
                findings_from_engine = await engine.verify_context(context, rule.params)

                # CONSTITUTIONAL FIX: Override engine-provided severity with rule's enforcement level
                # Engines may return hardcoded ERROR severity, but the rule's enforcement setting
                # takes precedence (advisory → INFO, reporting → WARNING, blocking → ERROR)
                for finding in findings_from_engine:
                    finding.severity = severity

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
                        file_path="none",
                    )
                )
        except Exception as e:
            logger.debug(
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
                    file_path="none",
                )
            )

        return findings

    # FILE-LEVEL ENGINES (ast_gate, glob_gate, regex_gate, llm_gate)
    logger.debug(
        "Rule %s: executing file-level engine '%s'",
        rule.rule_id,
        rule.engine,
    )

    try:
        files = context.get_files(include=rule.scope, exclude=rule.exclusions)
    except Exception as e:
        logger.error("Failed to get files for rule %s: %s", rule.rule_id, e)
        findings.append(
            AuditFinding(
                check_id=f"{rule.rule_id}.scope_error",
                severity=AuditSeverity.ERROR,
                message=f"Rule '{rule.rule_id}' failed to resolve file scope: {e}",
                file_path="none",
            )
        )
        return findings

    severity = _map_enforcement_to_severity(rule.enforcement)

    # Execute engine on each file
    for file_path in files:
        try:
            # FIXED: Added 'await' because BaseEngine.verify is now async.
            # This allows engines to perform I/O without hijacking the loop.
            result = await engine.verify(file_path, rule.params)

            if not result.ok:
                if result.violations:
                    for violation_msg in result.violations:
                        findings.append(
                            AuditFinding(
                                check_id=rule.rule_id,
                                severity=severity,
                                message=violation_msg,
                                file_path=str(file_path.relative_to(context.repo_path)),
                            )
                        )
                else:
                    findings.append(
                        AuditFinding(
                            check_id=f"{rule.rule_id}.engine_error",
                            severity=AuditSeverity.ERROR,
                            message=f"{result.message} (file: {file_path.name})",
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
            continue

    return findings


__all__ = ["execute_rule"]
