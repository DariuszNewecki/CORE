# src/shared/models/grc_verdict.py
"""
The GRC verdict contract: a requirement evaluated over the whole corpus.

CONSTITUTIONAL ALIGNMENT (ADR-118):
- The unit of a GRC verdict is one ``RequirementVerdict`` per requirement,
  derived from the whole in-scope corpus — never per document (D1). Per-document
  signals (``grc_judge``) are inputs to it, never the reported surface.
- ``status`` is *what we found* (D3); ``evidence_class`` is *how we established
  it* (ADR-113, D6) — two orthogonal axes that never collapse into one. The
  evidence-class axis is reused verbatim from ``audit_models.EvidenceClass``.
- Silence is not a verdict; it is absence of evidence (D4). A document that says
  nothing about a requirement contributes nothing to its evidence pool — the
  verdict emerges from the pool, so "silent → satisfied" and "silent → gap" are
  both impossible by construction.
- ``applicability`` precedes scoring (D2): a ``not_covered`` only means anything
  once the framework is in-domain for the corpus. Out-of-domain requirements are
  surfaced as ``not_applicable`` with a reason, never silently dropped.

This module is a pure data contract — dataclasses + closed enums, mirroring
``audit_models``. No I/O, no logic; safe for any layer to import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .audit_models import EvidenceClass


# ID: 71db8a31-d948-42c3-8bc4-9e605fa40b42
class Applicability(str, Enum):
    """Whether a framework/requirement is in domain for this corpus (ADR-118 D2).

    The applicability gate's verdict, established before any requirement is
    scored. It is itself a judged/attested call (not a fact) and carries its own
    evidence class on the verdict. Stored as its lowercase string value.

    - ``in_scope``     — the corpus reads as the framework's domain; score it.
    - ``out_of_scope`` — the framework is out of domain for this corpus; the
      requirement becomes ``not_applicable`` (surfaced with a reason, D2).
    - ``uncertain``    — domain fit could not be established with confidence;
      defer to the operator's confirm step rather than guessing either way.
    """

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    UNCERTAIN = "uncertain"

    def __str__(self) -> str:
        return self.value


# ID: e74433eb-7ded-431d-845f-f0944929d726
class RequirementStatus(str, Enum):
    """The outcome of evaluating one requirement over the corpus (ADR-118 D3).

    The reported verdict surface — richer than the per-document
    gap/met/pending_ai vocabulary it subsumes. Stored as its lowercase string
    value. Three bands:

    - **pass** — ``satisfied`` (covered authoritatively) and ``not_applicable``
      (framework out of domain — *not* a gap).
    - **gap** — ``deficient`` (addressed but falls short), ``not_covered`` (no
      evidence anywhere in scope — the structural gap), and
      ``covered_unauthoritatively`` (evidence exists, but not in the document
      expected to own it — the authority gap ITAM's ``Primary_Deficit`` surfaces).
    - **non-verdict** — ``needs_human`` (the attestation lane) and
      ``unavailable`` (a verdict could not be established: transient AI failure
      / engine crash). Neither is ever a gap.
    """

    SATISFIED = "satisfied"
    DEFICIENT = "deficient"
    NOT_COVERED = "not_covered"
    COVERED_UNAUTHORITATIVELY = "covered_unauthoritatively"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_HUMAN = "needs_human"
    UNAVAILABLE = "unavailable"

    def __str__(self) -> str:
        return self.value


# The statuses that constitute a compliance gap (the actionable signal). Kept as
# a module constant so the gap-count surface has one definition, not a predicate
# re-derived at every call site.
_GAP_STATUSES = frozenset(
    {
        RequirementStatus.DEFICIENT,
        RequirementStatus.NOT_COVERED,
        RequirementStatus.COVERED_UNAUTHORITATIVELY,
    }
)

# Statuses where no determinate verdict was reached — not a pass, not a gap.
_NON_VERDICT_STATUSES = frozenset(
    {
        RequirementStatus.NEEDS_HUMAN,
        RequirementStatus.UNAVAILABLE,
    }
)


@dataclass
# ID: 851c5ac2-f68c-4457-9d68-e461937cb371
class ApplicabilityAssessment:
    """The applicability gate's verdict for one framework over a corpus (D2).

    Established before any requirement is scored. ``applicability`` is itself a
    judged/attested call (not a fact), so it carries its own ``evidence_class``.
    CORE MUST NOT silently assume domain fit: anything other than ``in_scope``
    requires operator confirmation before scoring (``requires_confirmation``).
    """

    framework_id: str
    applicability: Applicability
    evidence_class: EvidenceClass
    detected_domains: list[str] = field(default_factory=list)
    rationale: str = ""

    @property
    # ID: 54064e9f-0086-482a-849c-db10cadb8726
    def requires_confirmation(self) -> bool:
        """True unless the framework reads as clearly in-domain.

        ``out_of_scope`` and ``uncertain`` both demand an operator confirm step;
        only ``in_scope`` may proceed to scoring without one (D2).
        """
        return self.applicability is not Applicability.IN_SCOPE


@dataclass
# ID: a555a36e-2b37-4ba8-a76f-9fbd2056ed40
class EvidenceItem:
    """One localized piece of evidence behind a verdict (ADR-118 D5).

    Answers not just "is this covered" but "where, and how authoritatively."
    The precedent is ITAM's evidence mass + authority concentration.

    - ``document``  — the corpus document the evidence came from (relative path).
    - ``relevance`` — similarity / retrieval score in ``[0, 1]``; how strongly
      this document speaks to the requirement.
    - ``authority`` — authority signal in ``[0, 1]``; whether it is the document
      *expected* to own the requirement (drives ``covered_unauthoritatively``).
      ``None`` when the catalog carries no expected-placement metadata — coverage
      is then known but placement is not (degrades gracefully to ``satisfied``).
    - ``cite``      — a short excerpt / citation supporting the verdict.
    """

    document: str
    relevance: float
    authority: float | None = None
    cite: str = ""


@dataclass
# ID: 9d16d21b-09a3-42d0-9f3f-b233d28dc719
class RequirementVerdict:
    """One requirement's verdict over the whole in-scope corpus (ADR-118 D1).

    The reported unit of a GRC gap-analysis. Carries both honesty axes: ``status``
    (what we found, D3) and ``evidence_class`` (how we established it, ADR-113 /
    D6). ``evidence`` localizes the verdict to the documents that produced it
    (D5). ``statement`` is a denormalized copy of the requirement text, carried
    for rendering without re-resolving the catalog.
    """

    requirement_id: str
    applicability: Applicability
    status: RequirementStatus
    evidence_class: EvidenceClass
    rationale: str = ""
    statement: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)

    @property
    # ID: c593e321-b20c-44af-8d33-d8510493e22b
    def is_gap(self) -> bool:
        """True when this verdict is an actionable compliance gap (D3 gap band)."""
        return self.status in _GAP_STATUSES

    @property
    # ID: 482e501b-270f-4e44-9c84-1799acdd7b42
    def is_verdict(self) -> bool:
        """True when a determinate verdict was reached (pass or gap, not deferred).

        ``needs_human`` and ``unavailable`` are non-verdicts: the requirement was
        neither passed nor failed, only handed off or left unestablished.
        """
        return self.status not in _NON_VERDICT_STATUSES
