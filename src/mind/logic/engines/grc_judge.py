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
    """

    engine_id = "grc_judge"
    evidence_class = EvidenceClass.JUDGED  # ADR-113: AI/semantic verdict

    def __init__(
        self,
        path_resolver: PathResolver,
        llm_client: LLMClientProtocol,
    ):
        self._paths = path_resolver
        self.llm = llm_client
        self._prompt_model = PromptModel.load("grc_judge")

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
        """
        instruction = params.get("instruction", "")
        rationale = params.get("rationale", "No control reference provided.")

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

        try:
            response_text = await self._prompt_model.invoke(
                context={
                    "instruction": instruction,
                    "rationale": rationale,
                    "content": content,
                },
                client=self.llm,
                user_id="grc_judge_engine",
            )
            # Canonical extractor: tolerates ```-fenced / wrapped JSON that a
            # raw json.loads would reject (which would otherwise surface as a
            # false "AI offline"). Raises on genuinely unparseable output →
            # caught below as ENFORCEMENT_UNAVAILABLE.
            result_data = extract_json(response_text)

            satisfied = not result_data.get("violation", False)
            reasoning = result_data.get("reasoning", "")
            finding = result_data.get("finding")

            if satisfied:
                return EngineResult(
                    ok=True,
                    message="Requirement satisfied by the document corpus.",
                    violations=[],
                    engine_id=self.engine_id,
                )
            gap = finding or reasoning or "Requirement not satisfied."
            return EngineResult(
                ok=False,
                message=f"Compliance gap: {gap}",
                violations=[gap],
                engine_id=self.engine_id,
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
