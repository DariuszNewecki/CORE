# src/mind/governance/rule_executor.py

from __future__ import annotations

from typing import TYPE_CHECKING

from mind.logic.engines.base import normalize_violation
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


# #306/#307: marker the llm_gate engine emits when an LLM call fails for
# infrastructure reasons (timeout, connection error, rate limit). We
# aggregate these into one WARNING per rule rather than emitting one
# finding per file, because per-file findings get claimed by the
# autonomous remediation loop and produce churn against unmapped rules.
# The engine still surfaces a real per-file violation when the LLM
# returns a legitimate "violation: true" verdict — that path is unaffected.
_TRANSIENT_LLM_FAILURE_MARKER = "SYSTEM_ERROR_AI_OFFLINE"


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
    rule: ExecutableRule,
    context: AuditorContext,
    *,
    file_filter: frozenset[str] | None = None,
    prior_findings: list[AuditFinding] | None = None,
) -> list[AuditFinding]:
    """
    Execute a single rule and return findings.

    Args:
        rule: The rule to execute.
        context: AuditorContext with repo and policy info.
        file_filter: Optional set of repo-relative POSIX file paths
            scoping the per-file iteration. When provided (#279), the
            rule runs only against the intersection of its declared
            scope and this set; an empty intersection produces no
            findings (no work). Context-level rules cannot be scoped to
            a file list and are skipped with a warning when this filter
            is set — the caller's per-file gate cannot meaningfully
            constrain a cross-file check.
        prior_findings: Findings accumulated by earlier rules in the
            current audit run. Required when this rule declares
            requires_findings_from (ADR-043 D2): the per-file scope is
            further narrowed to files that already have findings under
            the listed rule IDs. None or an empty list when the rule
            has no preconditions; the audit driver topologically orders
            rules so preconditions execute first
            (rule_extractor._topologically_sort_rules).
    """
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

    # #307: when an llm_gate rule falls back to LLMGateStubEngine (no LLM
    # client wired), emit ONE WARNING for the rule and skip per-file
    # evaluation. Without this, llm_gate rules silently produce zero
    # findings — indistinguishable from a real pass. Per-file evaluation
    # is also skipped because the stub returns ok=True for every file
    # and would generate no findings anyway, while the per-rule WARNING
    # is what the governor actually needs to see.
    from mind.logic.engines.llm_gate_stub import LLMGateStubEngine

    if isinstance(engine, LLMGateStubEngine):
        return [
            AuditFinding(
                check_id=rule.rule_id,
                severity=AuditSeverity.WARNING,
                message=(
                    f"Rule '{rule.rule_id}' uses engine '{rule.engine}' which "
                    "is not operational in this run (no LLM client wired). "
                    "Audit signal for this rule is muted until the wiring is "
                    "available — see GitHub #306."
                ),
                file_path="none",
                context={
                    "engine_id": rule.engine,
                    "stub": True,
                    "reason": "no_llm_client",
                },
            )
        ]

    if rule.is_context_level:
        # ADR-279 / #279: --files scopes per-file checks; context-level
        # rules look at the whole repo and can't be meaningfully filtered
        # to a subset, so skip with a warning when a file filter is
        # active. This keeps pre-commit-hook output focused on the
        # staged file set.
        if file_filter is not None:
            logger.info(
                "Skipping context-level rule %s under --files scope "
                "(engine=%s; cross-file check cannot be filtered)",
                rule.rule_id,
                rule.engine,
            )
            return findings
        if hasattr(engine, "verify_context"):
            severity = _map_enforcement_to_severity(rule.enforcement)
            engine_findings = await engine.verify_context(
                context,
                {**rule.params, "_scope_excludes": rule.exclusions},
            )
            for f in engine_findings:
                f.severity = severity
            findings.extend(engine_findings)
        return findings

    files = context.get_files(include=rule.scope, exclude=rule.exclusions)
    if file_filter is not None:
        # Intersect the rule's scope with the user's --files set. Empty
        # intersection produces no findings — the rule's scope didn't
        # cover any of the requested files (e.g. user passed
        # src/cli/foo.py against a rule scoped to src/api/**).
        files = [
            p
            for p in files
            if str(p.relative_to(context.repo_path)).replace("\\", "/") in file_filter
        ]
    if rule.requires_findings_from:
        # ADR-043 D2/D3: pre-selector narrowing. Run only against files
        # that have findings under the listed precondition rule IDs in
        # this audit run. Empty intersection produces no work and no
        # findings — the precondition rule did not fire on any in-scope
        # file. Aggregate findings with file_path="none" (transient LLM
        # failure WARNINGs, stub WARNINGs) cannot match a real path and
        # are filtered out naturally.
        requires_set = frozenset(rule.requires_findings_from)
        precondition_files = {
            f.file_path for f in (prior_findings or []) if f.check_id in requires_set
        }
        files = [
            p
            for p in files
            if str(p.relative_to(context.repo_path)).replace("\\", "/")
            in precondition_files
        ]
    severity = _map_enforcement_to_severity(rule.enforcement)
    transient_llm_failures: list[str] = []

    for file_path in files:
        try:
            # We add '_context' to the params so the Engine knows where to find the Cache
            params_with_context = {**rule.params, "_context": context}
            result = await engine.verify(file_path, params_with_context)
            if not result.ok:
                # #306/#307: transient LLM infrastructure failures are
                # aggregated, not emitted per-file. The marker is set by
                # LLMGateEngine when its LLM call fails for non-verdict
                # reasons (timeout, connection error, etc.).
                if any(
                    _TRANSIENT_LLM_FAILURE_MARKER in str(v) for v in result.violations
                ):
                    transient_llm_failures.append(
                        str(file_path.relative_to(context.repo_path))
                    )
                    continue
                for v in result.violations:
                    # Normalize whether engine emitted a bare string or a
                    # structured dict. Details (when present) flow into
                    # AuditFinding.context, which as_dict() aliases back
                    # to "details" in the JSON report.
                    msg, details = normalize_violation(v)
                    findings.append(
                        AuditFinding(
                            check_id=rule.rule_id,
                            severity=severity,
                            message=msg,
                            file_path=str(file_path.relative_to(context.repo_path)),
                            context=details,
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

    # #306/#307: emit one aggregate WARNING for transient LLM failures
    # accumulated during this rule's run. Bounds Blackboard pollution —
    # the autonomous remediation loop sees one finding per affected rule
    # instead of one per file. sample_files preserves enough signal for
    # the governor to investigate without churning the loop.
    if transient_llm_failures:
        findings.append(
            AuditFinding(
                check_id=rule.rule_id,
                severity=AuditSeverity.WARNING,
                message=(
                    f"Rule '{rule.rule_id}' LLM evaluation failed transiently "
                    f"on {len(transient_llm_failures)} file(s). Verdict for "
                    "those files is UNKNOWN until the LLM provider can keep "
                    "up with audit-scale throughput — see follow-up issue on "
                    "llm_gate concurrency/batching."
                ),
                file_path="none",
                context={
                    "finding_type": "LLM_TRANSIENT_FAILURE",
                    "engine_id": rule.engine,
                    "failure_count": len(transient_llm_failures),
                    "sample_files": transient_llm_failures[:5],
                },
            )
        )

    return findings
