# src/mind/governance/dispatch_integrity.py

"""Dispatch-integrity contract and ENFORCEMENT_FAILURE finding builders (#820).

Split out of ``rule_executor`` (ADR-095 modularity finding) with no behavior
change. ``declared_check_types`` reads an engine's published check_type
vocabulary fail-closed; the ``_*_finding`` builders construct the BLOCK
findings ``execute_rule`` returns when a rule cannot be honestly enforced.
Mind layer: pure, no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.executable_rule import ExecutableRule
    from mind.logic.engines.base import EngineResult


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
