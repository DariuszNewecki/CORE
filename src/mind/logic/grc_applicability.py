# src/mind/logic/grc_applicability.py

"""
GRC applicability gate — corpus-domain fit for a compliance framework (ADR-118 D2).

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Mirrors the grc_judge / llm_gate seam: a Mind component that reasons via an
  *injected* LLMClientProtocol. The client is never imported here; the corpus
  excerpt is supplied by the caller (Body samples the files — Mind does no I/O).
- The applicability verdict is JUDGED (ADR-113), never PROVEN: it is an AI
  reading of subject-matter fit, labelled as an opinion.
- Honest degradation (ADR-118 D2 "CORE MUST NOT silently assume domain fit"):
  any failure — no parseable verdict, an unknown label, a transient AI error —
  resolves to ``uncertain`` (which forces an operator confirm), never to a
  silent ``in_scope``.

WHY A SEPARATE COMPONENT (not a BaseEngine):
- The engines registry contract is per-file / per-context rule verification
  (``verify(file_path, params)``). The applicability gate is corpus-level and
  runs once per analysis, before any requirement is scored — a different shape.
  It is constructed directly by the GRC service with the injected client, not
  discovered by EngineRegistry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.ai.prompt_model import PromptModel
from shared.ai.response_parser import extract_json
from shared.logger import getLogger
from shared.models import Applicability, ApplicabilityAssessment, EvidenceClass


if TYPE_CHECKING:
    from shared.protocols.llm import LLMClientProtocol


logger = getLogger(__name__)


# ID: 8442974e-1817-4892-85c3-6250a672dee5
class GRCApplicabilityGate:
    """Judges whether a framework is in domain for a document corpus.

    The "detect" half of ADR-118's detect → suggest → confirm gate: it detects
    the corpus's domain(s) and labels the framework's fit. The "suggest" and
    "confirm" halves are the caller's (service/CLI) responsibility.
    """

    evidence_class = EvidenceClass.JUDGED  # ADR-113: an AI/semantic verdict

    # ID: 3da2a438-8ac4-4f14-a900-289d0dec5191
    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self.llm = llm_client
        self._prompt_model = PromptModel.load("grc_applicability")

    # ID: c4414ad0-33ab-4d27-98b7-965e72496436
    async def assess(
        self,
        framework_id: str,
        framework_descriptor: str,
        corpus_excerpt: str,
    ) -> ApplicabilityAssessment:
        """Judge whether ``framework_id`` is in domain for the sampled corpus.

        Args:
            framework_id: the catalog id (carried onto the assessment).
            framework_descriptor: a human-readable description of the framework
                (title / source / authority) — what domain it governs.
            corpus_excerpt: a representative sample of the corpus text. The
                caller (Body) reads and truncates the files; Mind only reasons.

        Returns an :class:`ApplicabilityAssessment`. On any failure the verdict
        degrades to ``uncertain`` — never a silent ``in_scope``.
        """
        try:
            response_text = await self._prompt_model.invoke(
                context={
                    "framework": framework_descriptor,
                    "corpus_excerpt": corpus_excerpt,
                },
                client=self.llm,
                user_id="grc_applicability_gate",
            )
            data = extract_json(response_text)
        except Exception as e:  # transient AI / unparseable → uncertain, honestly
            logger.warning(
                "GRC applicability gate could not judge %s: %s", framework_id, e
            )
            return ApplicabilityAssessment(
                framework_id=framework_id,
                applicability=Applicability.UNCERTAIN,
                evidence_class=self.evidence_class,
                detected_domains=[],
                rationale=f"Domain fit could not be established (AI unavailable): {e}",
            )

        applicability = self._coerce_applicability(data.get("applicability"))
        return ApplicabilityAssessment(
            framework_id=framework_id,
            applicability=applicability,
            evidence_class=self.evidence_class,
            detected_domains=self._split_domains(data.get("detected_domains")),
            rationale=str(data.get("reasoning") or "").strip(),
        )

    @staticmethod
    def _coerce_applicability(value: object) -> Applicability:
        """Map a raw label to the closed enum; unknown → uncertain (fail-closed)."""
        try:
            return Applicability(str(value).strip().lower())
        except (ValueError, AttributeError):
            return Applicability.UNCERTAIN

    @staticmethod
    def _split_domains(value: object) -> list[str]:
        """Normalize the model's domain field (comma-separated string) to a list."""
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if not value:
            return []
        return [part.strip() for part in str(value).split(",") if part.strip()]
