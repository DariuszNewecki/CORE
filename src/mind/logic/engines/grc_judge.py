# src/mind/logic/engines/grc_judge.py

"""
GRC Compliance Judge — semantic compliance assessment of documents.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Mirrors the established llm_gate seam: a Mind engine that reasons via an
  *injected* LLMClientProtocol (no Body/Will leakage; the client is provided by
  EngineRegistry, never imported here).
- Handles AI failures as 'UNAVAILABLE' for audit truthfulness — emits the
  shared SYSTEM_ERROR_AI_OFFLINE marker so rule_executor aggregates transient
  failures rather than miscounting them as gaps.
- Prompt governed via var/prompts/grc_judge/ PromptModel artifact.
- Internal corpus augmentation (ADR-122 D4): queries grc-internal-{framework_id}
  for top-3 passages; degrades gracefully when collection is absent or Qdrant
  is unreachable (EvidenceClass stays JUDGED regardless of augmentation).

WHY A SEPARATE ENGINE (not llm_gate):
- llm_gate is the constitutional *code* auditor; its prompt frames the model as
  a code reviewer and it carries the ADR-044 DB verdict-cache keyed on repo
  artifacts. The GRC gap-analysis corpus is the customer's documents (not CORE's
  repo, no DB session plumbed), and the verdict must read as a *compliance*
  assessment. Isolating it here keeps the constitutional audit untouched while
  letting the GRC judge speak the regulation-derived framing (ADR-116 catalogs).
- Evidence class is JUDGED (ADR-113), identical to llm_gate: an AI/semantic
  verdict, never PROVEN.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.ai.prompt_model import PromptModel
from shared.ai.response_parser import extract_json
from shared.logger import getLogger

from .base import BaseEngine, EngineResult, EvidenceClass


if TYPE_CHECKING:
    from shared.path_resolver import PathResolver
    from shared.protocols.llm import LLMClientProtocol


logger = getLogger(__name__)

# Same marker llm_gate uses; rule_executor aggregates these into one per-rule
# WARNING instead of a per-file pseudo-gap (see _TRANSIENT_LLM_FAILURE_MARKER).
_AI_OFFLINE_MARKER = "SYSTEM_ERROR_AI_OFFLINE"

# Number of internal corpus passages injected into the judge prompt (ADR-122 D4).
# Conservative: grounding without distortion. Code constant, not operator-tunable.
_INTERNAL_CORPUS_TOP_K = 3


# ID: 01d96d5a-7a9f-4c7d-93f8-7fc40542010a
class GRCJudgeEngine(BaseEngine):
    """
    Semantic compliance judge for GRC gap-analysis.

    Reads a document and decides whether it satisfies a single compliance
    requirement, returning a structured verdict. Speaks the same parameter
    vocabulary as llm_gate (``instruction`` / ``rationale`` / file ``content``)
    so a catalog requirement need only point its ``engine`` at ``grc_judge`` —
    no param rewrite — while the prompt reframes the task from code audit to
    compliance assessment.

    When ``params["framework_id"]`` is present (injected by ``load_catalog``),
    the engine queries the internal Qdrant corpus for up to 3 authoritative
    passages and prepends them to the prompt as "AUTHORITATIVE SOURCE CONTEXT"
    (ADR-122 D4). Absent/unreachable collection → silent degradation; the verdict
    remains valid and EvidenceClass stays JUDGED.
    """

    engine_id = "grc_judge"
    evidence_class = EvidenceClass.JUDGED  # ADR-113: AI/semantic verdict

    def __init__(
        self,
        path_resolver: PathResolver,
        llm_client: LLMClientProtocol,
        embedding_client: Any | None = None,
    ):
        self._paths = path_resolver
        self.llm = llm_client
        self._prompt_model = PromptModel.load("grc_judge")
        # Corpus augmentation: embedder is injected by EngineRegistry (DB-backed
        # resource registry, Vectorizer role). Absent = no augmentation; the
        # verdict remains valid and EvidenceClass stays JUDGED (ADR-122 D4).
        self._qdrant: Any | None = None
        self._embedder: Any | None = embedding_client

    # ID: 487eb9a1-e9bc-4359-8418-e900b2959569
    def _get_corpus_clients(self) -> tuple[Any, Any] | None:
        """Return (QdrantService, embedder) for corpus augmentation (ADR-122 D4).

        Embedder must be injected at construction via EngineRegistry — resolves
        through the DB-backed Vectorizer role, not from env/settings. Returns
        None when no embedder was injected (augmentation disabled; degrades
        gracefully — caller produces an unaugmented verdict).
        """
        if self._embedder is None:
            return None
        try:
            from shared.infrastructure.clients.qdrant_client import QdrantService

            if self._qdrant is None:
                self._qdrant = QdrantService()
            return self._qdrant, self._embedder
        except Exception as e:
            logger.debug("Corpus augmentation clients unavailable: %s", e)
            return None

    # ID: ebe70319-3ab2-4367-bdd0-918e9ddde4d3
    async def _retrieve_source_context(
        self, framework_id: str, instruction: str
    ) -> str:
        """Query ``grc-internal-{framework_id}`` for top-3 passages (ADR-122 D4).

        Returns a pre-formatted block suitable for ``{source_context}`` template
        substitution, or an empty string when the collection is absent, empty,
        or any error occurs (graceful degradation — D4 invariant).
        """
        clients = self._get_corpus_clients()
        if clients is None:
            return ""
        qdrant, embedder = clients
        try:
            query_vec = await embedder.get_embedding(instruction)
            hits = await qdrant.search(
                collection_name=f"grc-internal-{framework_id}",
                query_vector=query_vec,
                limit=_INTERNAL_CORPUS_TOP_K,
            )
            if not hits:
                return ""
            passages: list[str] = []
            for i, hit in enumerate(hits, 1):
                payload = hit.payload or {}
                text = payload.get("text", "")
                if not text:
                    continue
                label = (
                    payload.get("source_ref") or payload.get("section_id") or "excerpt"
                )
                passages.append(f"[{i}] {label}\n{text}")
            return "\n\n".join(passages)
        except Exception as e:
            logger.debug("Internal corpus search failed for %s: %s", framework_id, e)
            return ""

    # ID: 4d47dd81-0bb4-4d98-82bf-50d8df0208e4
    async def verify(
        self,
        file_path: Path,
        params: dict[str, Any],
    ) -> EngineResult:
        """Assess whether one document satisfies one compliance requirement.

        ``params["instruction"]`` is the requirement question (what the document
        must establish); ``params["rationale"]`` cites the control. A "violation"
        here means the document does NOT satisfy the requirement — i.e. a gap.

        When ``params["framework_id"]`` is present, the internal corpus is queried
        first and its top passages are injected into the prompt (ADR-122 D4).
        """
        instruction = params.get("instruction", "")
        rationale = params.get("rationale", "No control reference provided.")
        framework_id = params.get("framework_id", "")

        # Read the document safely off the event loop (ASYNC230).
        try:
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"IO Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # Augment with internal corpus passages (ADR-122 D4; degrades gracefully).
        source_context_block = ""
        if framework_id:
            passages = await self._retrieve_source_context(framework_id, instruction)
            if passages:
                source_context_block = (
                    f"AUTHORITATIVE SOURCE CONTEXT:\n---\n{passages}\n---\n\n"
                )

        try:
            response_text = await self._prompt_model.invoke(
                context={
                    "instruction": instruction,
                    "rationale": rationale,
                    "content": content,
                    "source_context": source_context_block,
                },
                client=self.llm,
                user_id="grc_judge_engine",
            )
            # Canonical extractor: tolerates ```-fenced / wrapped JSON that a
            # raw json.loads would reject (which would otherwise surface as a
            # false "AI offline"). Raises on genuinely unparseable output →
            # caught below as ENFORCEMENT_UNAVAILABLE.
            result_data = extract_json(response_text)

            violation = bool(result_data.get("violation", False))
            reasoning = str(result_data.get("reasoning") or "").strip()
            finding_text = result_data.get("finding")

            # Three-way coverage from the prompt (ADR-118 D4): satisfied / gap / silent.
            # "silent" means the document does not address this requirement — absence
            # of evidence, not a gap. Fall back to deriving from violation flag so
            # old-schema responses (without "coverage") degrade correctly.
            raw_coverage = result_data.get("coverage")
            if raw_coverage in ("satisfied", "gap", "silent"):
                coverage = raw_coverage
            else:
                coverage = "gap" if violation else "satisfied"

            extra: dict[str, object] = {"coverage": coverage, "reasoning": reasoning}
            if coverage == "gap":
                extra["finding"] = finding_text

            if coverage in ("satisfied", "silent"):
                return EngineResult(
                    ok=True,
                    message=(
                        "Document does not address this requirement (silent)."
                        if coverage == "silent"
                        else "Requirement satisfied by the document."
                    ),
                    violations=[],
                    engine_id=self.engine_id,
                    extra=extra,
                )
            gap = finding_text or reasoning or "Requirement not satisfied."
            return EngineResult(
                ok=False,
                message=f"Compliance gap: {gap}",
                violations=[gap],
                engine_id=self.engine_id,
                extra=extra,
            )
        except Exception as e:
            # AI unavailable / unparseable → enforcement UNAVAILABLE, not a gap.
            # The shared marker lets rule_executor aggregate this honestly.
            return EngineResult(
                ok=False,
                message=f"ENFORCEMENT_UNAVAILABLE: GRC judge reasoning failed: {e}",
                violations=[_AI_OFFLINE_MARKER],
                engine_id=self.engine_id,
            )
