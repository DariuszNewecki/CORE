# src/mind/governance/rule_executor.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mind.logic.engines.base import (
    EngineResult,
    extract_line_number,
    normalize_violation,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity, EvidenceClass


# #306/#307: marker the llm_gate engine emits when an LLM call fails for
# infrastructure reasons (timeout, connection error, rate limit). We
# aggregate these into one WARNING per rule rather than emitting one
# finding per file, because per-file findings get claimed by the
# autonomous remediation loop and produce churn against unmapped rules.
# The engine still surfaces a real per-file violation when the LLM
# returns a legitimate "violation: true" verdict — that path is unaffected.
_TRANSIENT_LLM_FAILURE_MARKER = "SYSTEM_ERROR_AI_OFFLINE"

# ADR-039 Option F (2026-06-29): evaluation-level cache extends the parse
# cache (Option E, audit_context._AST_CACHE) one layer deeper. Where Option E
# skips read_text()+ast.parse() for unchanged files, Option F skips
# engine.verify() entirely. Cache key: (rule_id, abs_path_str,
# rule_content_hash, mtime_ns, size). Content-identity keying (not git-ref
# keying) ensures uncommitted edits are caught on the same cycle they occur —
# consistent with Option E. A changed file produces a different key and misses;
# an edited rule's rule_content_hash changes and invalidates all its entries.
# llm_gate rules are excluded: they carry their own DB-backed verdict cache
# (ADR-044) and their verdicts depend on factors beyond file+rule content
# identity (LLM state, model selection). ENFORCEMENT_FAILURE and transient LLM
# failure results are never cached — they are infrastructure signals that must
# re-evaluate each cycle.
_EVAL_CACHE: dict[tuple[str, str, str, int, int], list[AuditFinding]] = {}
_EVAL_CACHE_MAX_ENTRIES: int = 10_000
# Engines whose verdicts depend on state outside file+rule content identity.
_EVAL_CACHE_SKIP_ENGINES: frozenset[str] = frozenset({"llm_gate"})


def _eval_cache_store(
    key: tuple[str, str, str, int, int],
    findings: list[AuditFinding],
) -> None:
    """Store per-file evaluation findings under their content-identity key, FIFO-evicting past the cap."""
    if key in _EVAL_CACHE:
        del _EVAL_CACHE[key]
    elif len(_EVAL_CACHE) >= _EVAL_CACHE_MAX_ENTRIES:
        del _EVAL_CACHE[next(iter(_EVAL_CACHE))]
    _EVAL_CACHE[key] = findings


# ID: 3f8a1d2e-9b7c-4e5f-a6d0-1c2b3e4f5a6b
def clear_eval_cache() -> None:
    """Discard all evaluation-level cache entries.

    Intended for tests that need a cold-start guarantee and for
    force-reaudit paths where the caller explicitly wants every file
    re-evaluated regardless of content identity.
    """
    _EVAL_CACHE.clear()


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from mind.governance.executable_rule import ExecutableRule

logger = getLogger(__name__)


# ID: 8c1f0a52-4e7d-4b93-a06c-2d9f7b31e845
class VocabularyUnavailableError(Exception):
    """An engine's check_type vocabulary could not be read.

    Raised rather than returned so the condition cannot be mistaken for
    "this engine declares no vocabulary" — the two are opposite verdicts and
    collapsing them re-opens the fail-open hole.
    """


# ID: 944875ec-f3eb-44d1-aff1-ba17a2fed502
def declared_check_types(engine: Any) -> frozenset[str] | None:
    """Return the check_type vocabulary an engine declares, or None if it declares none.

    Two conventions exist in the engine tree and both are honoured: a
    ``supported_check_types()`` classmethod (knowledge_gate) and a
    ``_SUPPORTED_CHECK_TYPES`` ClassVar (ast_gate). An engine that declares
    neither is not validated — the contract is opt-in, because only an engine
    that publishes its vocabulary can be held to it. Declaring is what buys
    the protection.

    Fail-closed on both edges (#820 follow-up):

    - A vocabulary accessor that *raises* must not be read as "declares
      nothing". Swallowing the error would silently disable the very contract
      this function exists to enforce — the failure mode #820 was opened for.
      ``VocabularyUnavailableError`` propagates so the caller can BLOCK.
    - An **empty** ``_SUPPORTED_CHECK_TYPES`` is a declaration ("I dispatch no
      named check_types"), not an absence of one. Testing it by truthiness
      conflated the two and handed a fully-inert engine an exemption.
    """
    declared = getattr(engine, "supported_check_types", None)
    if callable(declared):
        try:
            return frozenset(declared())
        except Exception as exc:
            raise VocabularyUnavailableError(
                f"engine '{type(engine).__name__}' failed to publish its "
                f"check_type vocabulary: {exc}"
            ) from exc
    classvar = getattr(engine, "_SUPPORTED_CHECK_TYPES", None)
    if classvar is not None:
        return frozenset(classvar)
    return None


def _unsupported_check_type_finding(
    rule: ExecutableRule, check_type: object, declared: frozenset[str]
) -> AuditFinding:
    """Build the BLOCK finding for a rule whose check_type its engine cannot dispatch.

    Covers both shapes: a name the engine does not implement, and no name at
    all. A missing check_type against a finite vocabulary is the more
    dangerous of the two — for a context-level engine it reaches
    ``verify_context()``, whose empty result reads as a clean pass.
    """
    fault = (
        "declares no check_type"
        if check_type is None
        else f"declares check_type {check_type!r}, which"
    )
    return AuditFinding(
        check_id=f"{rule.rule_id}.enforcement_failure",
        severity=AuditSeverity.BLOCK,
        message=(
            f"ENFORCEMENT_FAILURE: Rule {fault} "
            f"engine '{rule.engine}' does not implement. The rule enforces nothing. "
            f"Compliance status UNKNOWN — treat as non-compliant until fixed. "
            f"Engine supports: {', '.join(sorted(declared)) or '(nothing)'}."
        ),
        file_path="none",
        context={
            "finding_type": "ENFORCEMENT_FAILURE",
            "engine": rule.engine,
            "policy_id": rule.policy_id,
            "declared_check_type": check_type,
            "supported_check_types": sorted(declared),
        },
    )


def _vocabulary_unavailable_finding(
    rule: ExecutableRule, error: Exception
) -> AuditFinding:
    """Build the BLOCK finding for an engine that could not publish its vocabulary.

    Without this the accessor's failure would degrade to "declares nothing",
    which exempts the engine from dispatch validation entirely — a fail-open
    path through the fail-closed contract.
    """
    return AuditFinding(
        check_id=f"{rule.rule_id}.enforcement_failure",
        severity=AuditSeverity.BLOCK,
        message=(
            f"ENFORCEMENT_FAILURE: Engine '{rule.engine}' could not publish its "
            f"check_type vocabulary ({error}), so dispatch integrity cannot be "
            f"verified. Compliance status UNKNOWN — treat as non-compliant until "
            f"fixed."
        ),
        file_path="none",
        context={
            "finding_type": "ENFORCEMENT_FAILURE",
            "engine": rule.engine,
            "policy_id": rule.policy_id,
            "vocabulary_error": str(error),
        },
    )


def _empty_violation_finding(
    rule: ExecutableRule, result: EngineResult, rel_path: str
) -> AuditFinding:
    """Build the BLOCK finding for an engine that failed without naming a violation.

    ``execute_rule`` materialises findings by iterating ``result.violations``.
    An engine returning ``ok=False`` with an empty list therefore produced a
    verdict of "failed" that renders as nothing at all — indistinguishable from
    a clean pass. ast_gate's own #588 unknown-check_type guard has exactly this
    shape, which is why that fix has been invisible since it landed.
    """
    message = getattr(result, "message", "") or "engine reported failure without detail"
    return AuditFinding(
        check_id=f"{rule.rule_id}.enforcement_failure",
        severity=AuditSeverity.BLOCK,
        message=(
            f"ENFORCEMENT_FAILURE: Engine '{rule.engine}' returned ok=False with no "
            f"violations on {rel_path}: {message}. A failure without evidence cannot "
            f"be adjudicated — treat as non-compliant until fixed."
        ),
        file_path=rel_path,
        context={
            "finding_type": "ENFORCEMENT_FAILURE",
            "engine": rule.engine,
            "policy_id": rule.policy_id,
            "engine_message": message,
        },
    )


def _map_enforcement_to_severity(enforcement: str) -> AuditSeverity:
    # #432: `reporting` is informational by intent — surfacing a fact, not
    # demanding action. It must not inflate the HIGH bucket alongside true
    # warnings. `warning` stays HIGH for callers that want noisy-but-non-
    # blocking signal even though no rule in the current tree uses it.
    e = enforcement.lower()
    if e in ("blocking", "error"):
        return AuditSeverity.BLOCK
    if e == "warning":
        return AuditSeverity.HIGH
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
                severity=AuditSeverity.BLOCK,
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
                severity=AuditSeverity.HIGH,
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

    # #820 contract 1 — dispatch integrity. A rule naming a check_type its
    # engine cannot dispatch enforces nothing, and does so silently: every
    # named-dispatch engine falls through to an empty result for an
    # unrecognised name. Four `capability.taxonomy.*` rules sat blocking-but-
    # inert this way since 4849af15 (March 2026), against a
    # `capability_taxonomy_whitelist` handler that never landed. Validate
    # before dispatch so the drift is a verdict, not a silence.
    #
    # Opt-in by design: only engines that publish a check_type vocabulary are
    # checked (see declared_check_types). Engines that publish nothing are
    # unchanged — this adds a contract, it does not retrofit one.
    #
    # A *missing* check_type is included, not exempted: against an engine
    # publishing a finite vocabulary, dispatching on nothing selects nothing.
    # For context-level engines that lands in verify_context(), whose empty
    # result is indistinguishable from a clean pass — the per-file
    # ok=False/violations=[] contract below cannot see it.
    try:
        declared = declared_check_types(engine)
    except VocabularyUnavailableError as exc:
        logger.error(
            "ENFORCEMENT_FAILURE: Rule %s — engine %s could not publish its "
            "check_type vocabulary: %s",
            rule.rule_id,
            rule.engine,
            exc,
        )
        return [_vocabulary_unavailable_finding(rule, exc)]

    if declared is not None:
        rule_check_type = rule.params.get("check_type")
        if rule_check_type is None or rule_check_type not in declared:
            logger.error(
                "ENFORCEMENT_FAILURE: Rule %s declares check_type %r unsupported "
                "by engine %s (supports: %s)",
                rule.rule_id,
                rule_check_type,
                rule.engine,
                ", ".join(sorted(declared)),
            )
            return [_unsupported_check_type_finding(rule, rule_check_type, declared)]

    # ADR-113: the producing engine is the authority on how it establishes a
    # verdict. Stamp its declared class onto every genuine-verdict finding
    # below. Crash / unknown findings are NOT stamped — they keep the
    # AuditFinding default (ATTESTED = "needs a human"), which is the honest
    # label for a verdict we could not actually reach (D3 fail-closed).
    engine_evidence_class = getattr(engine, "evidence_class", EvidenceClass.ATTESTED)

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
                # ADR-113 D3 fail-closed: an engine can return a finding from
                # inside verify_context() that represents "could not
                # evaluate" rather than a genuine verdict (context-level
                # engines have no early-return path for this — unlike the
                # unsupported-check_type/vocabulary-unavailable guards above,
                # which return before this loop and keep AuditFinding's
                # ATTESTED default). Promoting such a finding to the engine's
                # declared evidence_class would render an unevaluated source
                # indistinguishable from a proven violation. Findings that
                # self-identify via context["finding_type"] ==
                # "ENFORCEMENT_FAILURE" keep the ATTESTED default; only
                # genuine verdicts get stamped with the engine's class.
                if f.context.get("finding_type") != "ENFORCEMENT_FAILURE":
                    f.evidence_class = engine_evidence_class  # ADR-113
                # Restore check_id == rule.rule_id invariant (#485). The per-file
                # path at the bottom of this function constructs AuditFinding with
                # check_id=rule.rule_id; the context-level path historically passed
                # engine-set check_ids through unmodified, letting them drift to
                # `<engine_id>.<check_type>` shapes (e.g. cli_gate.resource_first
                # for rule cli.resource_first). That drift made AuditViolationSensor
                # dedup work only by string-prefix coincidence. Engine identity is
                # still recoverable via the rule's mapping in .intent/; per-finding
                # engine attribution stays available through f.context if a check
                # records it there.
                f.check_id = rule.rule_id
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
    # #309: store (rel_path, underlying_error_message) pairs so the
    # aggregate finding preserves the engine's diagnostic string.
    transient_llm_failures: list[tuple[str, str]] = []

    # ADR-039 Option F: evaluation cache is active when the engine's verdicts
    # are content-deterministic and the rule has a non-empty content hash.
    use_eval_cache = rule.engine not in _EVAL_CACHE_SKIP_ENGINES and bool(
        rule.rule_content_hash
    )

    for file_path in files:
        try:
            # ADR-039 Option F: stat the file for a content-identity cache
            # lookup before dispatching engine.verify(). A hit means this
            # (rule, file, rule-definition, file-content) combination was
            # evaluated in a prior cycle and the result is still valid — skip
            # the engine entirely and carry the cached findings forward.
            if use_eval_cache:
                try:
                    st = file_path.stat()
                    eval_key: tuple[str, str, str, int, int] | None = (
                        rule.rule_id,
                        str(file_path),
                        rule.rule_content_hash,
                        st.st_mtime_ns,
                        st.st_size,
                    )
                except OSError:
                    eval_key = None
                else:
                    if eval_key in _EVAL_CACHE:
                        findings.extend(_EVAL_CACHE[eval_key])
                        continue
            else:
                eval_key = None

            # We add '_context' to the params so the Engine knows where to find the Cache.
            # ADR-044: thread rule identity, content hash, and force-llm flag
            # through so the llm_gate engine can perform DB-backed verdict
            # caching. Underscored keys are engine-protocol fields, not rule
            # params — engines ignore them if they don't care.
            params_with_context = {
                **rule.params,
                "_context": context,
                "_rule_id": rule.rule_id,
                "_rule_content_hash": rule.rule_content_hash,
                "_force_llm": getattr(context, "force_llm", False),
            }
            result = await engine.verify(file_path, params_with_context)
            if not result.ok:
                # #306/#307: transient LLM infrastructure failures are
                # aggregated, not emitted per-file. The marker is set by
                # LLMGateEngine when its LLM call fails for non-verdict
                # reasons (timeout, connection error, etc.). Never cached —
                # the infrastructure condition may clear next cycle.
                marker_violation = next(
                    (
                        v
                        for v in result.violations
                        if _TRANSIENT_LLM_FAILURE_MARKER in str(v)
                    ),
                    None,
                )
                if marker_violation is not None:
                    rel_path = str(file_path.relative_to(context.repo_path))
                    err_msg, _ = normalize_violation(marker_violation)
                    transient_llm_failures.append((rel_path, err_msg))
                    continue
                # #820 contract 2 — result truthfulness. Findings below are
                # materialised solely by iterating result.violations, so an
                # engine that says ok=False while naming nothing renders as a
                # clean pass. Never cached: like a crash, this is an
                # infrastructure signal that must re-evaluate each cycle.
                if not result.violations:
                    findings.append(
                        _empty_violation_finding(
                            rule,
                            result,
                            str(file_path.relative_to(context.repo_path)),
                        )
                    )
                    continue
                file_findings: list[AuditFinding] = []
                for v in result.violations:
                    # Normalize whether engine emitted a bare string or a
                    # structured dict. Details (when present) flow into
                    # AuditFinding.context, which as_dict() aliases back
                    # to "details" in the JSON report.
                    msg, details = normalize_violation(v)
                    # #548: extract the line number from structured details
                    # or from a "Line N" pattern in the message so GitHub
                    # inline annotations land at the actual violation line
                    # rather than the file-level fallback.
                    line_number = extract_line_number(msg, details)
                    file_findings.append(
                        AuditFinding(
                            check_id=rule.rule_id,
                            severity=severity,
                            message=msg,
                            file_path=str(file_path.relative_to(context.repo_path)),
                            line_number=line_number,
                            context=details,
                            evidence_class=engine_evidence_class,  # ADR-113
                        )
                    )
                findings.extend(file_findings)
                if eval_key is not None:
                    _eval_cache_store(eval_key, file_findings)
            else:
                # Clean file — cache the empty result so the next cycle skips
                # evaluation entirely for this (rule, file) pair.
                if eval_key is not None:
                    _eval_cache_store(eval_key, [])
        except Exception as e:
            # HARDENING P0.1 (per-file): Engine crash on a single file →
            # ENFORCEMENT_FAILURE finding. A crashing per-file check is NOT
            # a passing check. Silent continue would make this rule
            # indistinguishable from a clean pass for this file.
            # Never cached — the crash may be transient or the file in flux.
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
                    severity=AuditSeverity.BLOCK,
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
        # #309: deduplicate underlying error strings. A single root cause
        # (e.g. the prompt-contract mismatch that made #308 look transient)
        # shows up as one entry; a true intermittent shows many. Visible
        # from the message without reading every per-file sample.
        unique_errors = sorted({err for _, err in transient_llm_failures})
        findings.append(
            AuditFinding(
                check_id=rule.rule_id,
                severity=AuditSeverity.HIGH,
                message=(
                    f"Rule '{rule.rule_id}' LLM evaluation failed transiently "
                    f"on {len(transient_llm_failures)} file(s) "
                    f"({len(unique_errors)} unique error(s)). Verdict for "
                    "those files is UNKNOWN until the LLM provider can keep "
                    "up with audit-scale throughput — see follow-up issue on "
                    "llm_gate concurrency/batching."
                ),
                file_path="none",
                context={
                    "finding_type": "LLM_TRANSIENT_FAILURE",
                    "engine_id": rule.engine,
                    "failure_count": len(transient_llm_failures),
                    "sample_files": [path for path, _ in transient_llm_failures[:5]],
                    "sample_errors": [
                        {"file": path, "error": err}
                        for path, err in transient_llm_failures[:5]
                    ],
                    "unique_error_messages": unique_errors[:5],
                },
            )
        )

    return findings
