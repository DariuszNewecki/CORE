# src/mind/governance/rule_executor.py

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)


def _map_enforcement_to_severity(enforcement: str) -> AuditSeverity:
    e = enforcement.lower()
    if e in ("blocking", "error"):
        return AuditSeverity.ERROR
    if e in ("reporting", "warning"):
        return AuditSeverity.WARNING
    return AuditSeverity.INFO


# ID: d28e3c01-6744-4875-8511-0d216a07964a
async def execute_rule(
    rule: ExecutableRule, context: AuditorContext
) -> list[AuditFinding]:
    from mind.logic.engines.registry import EngineRegistry

    findings: list[AuditFinding] = []

    try:
        engine = EngineRegistry.get(rule.engine)
    except ValueError as e:
        return [
            AuditFinding(
                check_id=f"{rule.rule_id}.engine_missing",
                severity=AuditSeverity.ERROR,
                message=str(e),
                file_path="none",
            )
        ]

    if rule.is_context_level:
        if hasattr(engine, "verify_context"):
            severity = _map_enforcement_to_severity(rule.enforcement)
            engine_findings = await engine.verify_context(context, rule.params)
            for f in engine_findings:
                f.severity = severity
            findings.extend(engine_findings)
        return findings

    files = context.get_files(include=rule.scope, exclude=rule.exclusions)
    severity = _map_enforcement_to_severity(rule.enforcement)

    for file_path in files:
        try:
            # We add '_context' to the params so the Engine knows where to find the Cache
            params_with_context = {**rule.params, "_context": context}
            result = await engine.verify(file_path, params_with_context)
            if not result.ok:
                for msg in result.violations:
                    findings.append(
                        AuditFinding(
                            check_id=rule.rule_id,
                            severity=severity,
                            message=msg,
                            file_path=str(file_path.relative_to(context.repo_path)),
                        )
                    )
        except Exception as e:
            # HARDENING P0.1 (per-file): Engine crash on a single file →
            # ENFORCEMENT_FAILURE finding. A crashing per-file check is NOT
            # a passing check. Silent continue would make this rule
            # indistinguishable from a clean pass for this file.
            logger.error(
                "ENFORCEMENT_FAILURE: Rule %s crashed on file %s: %s",
                rule.rule_id,
                file_path,
                e,
                exc_info=True,
            )
            findings.append(
                AuditFinding(
                    check_id=f"{rule.rule_id}.enforcement_failure",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"ENFORCEMENT_FAILURE: Rule crashed on {file_path}: {e}. "
                        f"Compliance status UNKNOWN — treat as non-compliant until fixed."
                    ),
                    file_path=str(file_path.relative_to(context.repo_path)),
                    context={
                        "finding_type": "ENFORCEMENT_FAILURE",
                        "engine": rule.engine,
                        "policy_id": rule.policy_id,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                )
            )
            continue

    return findings
