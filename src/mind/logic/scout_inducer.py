# src/mind/logic/scout_inducer.py

"""
Scout rule inducer — Mind component (ADR-119 D3).

Receives structural signals extracted from a target repository and proposes
candidate governance observations — what to govern and why, grounded in the
repo's own patterns. The LLM does not specify enforcement mechanics (engine,
params, scope); that mapping is the caller's responsibility via the enforcement
catalog. I/O-free: all file sampling and catalog loading is done by the caller
(CLI layer). The LLM client is injected by the caller; Mind reasons but does
not import client infrastructure directly.

Follows the GRCApplicabilityGate pattern: failures degrade to an empty
candidate list — never a silent proposal set or a crash.

CONSTITUTIONAL ALIGNMENT:
- 'architecture.boundary.llm_client_access': LLMClientProtocol is imported
  under TYPE_CHECKING only — not invoked at import time (type_checking_exempt).
- 'architecture.layers.no_mind_execution': no I/O, no file reads. The caller
  supplies the signals string; this component only reasons over it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.ai.prompt_model import PromptModel
from shared.ai.response_parser import extract_json
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.protocols.llm import LLMClientProtocol


logger = getLogger(__name__)


# ID: d3998b47-12b1-4fc0-8f35-05b569e7511d
class ScoutInducer:
    """Proposes candidate governance rules from repository structural signals.

    The "suggest" half of ADR-119's detect → suggest → confirm induction loop.
    Receives pre-computed signals (the "detect" half is the caller's job), calls
    the LLM via PromptModel, and returns validated candidate proposals. Any
    failure degrades to an empty list — callers always fall back to the
    universal menu (ADR-119 D7).
    """

    # ID: 0ad94e57-414a-4c01-9b7b-7c29b61797c3
    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self.llm = llm_client
        self._prompt_model = PromptModel.load("scout_rule_inducer")

    # ID: a0ed4bfb-2093-44a6-ac80-5964956ae0a2
    async def propose(self, code_signals: str) -> list[dict[str, Any]]:
        """Propose governance observations from repository structural signals.

        Each candidate describes what to govern and why, grounded in observed
        code patterns. Enforcement mechanics (engine, params, scope) are absent
        from the output — the CLI layer maps observations to enforcement via the
        catalog after this call returns.

        Args:
            code_signals: Formatted string of signals extracted from the target
                repo — file counts, pattern prevalence, and representative code
                excerpts. Produced by the CLI detect phase; never read here.

        Returns:
            List of candidate observation dicts (rule_id, statement, enforcement,
            rationale, evidence_sample, ramp_note). Empty on any AI failure —
            callers must handle the empty case by falling back to the universal menu.
        """
        try:
            response_text = await self._prompt_model.invoke(
                context={"code_signals": code_signals},
                client=self.llm,
                user_id="scout_rule_inducer",
            )
            data = extract_json(response_text)
        except Exception as e:
            logger.warning("ScoutInducer: LLM call failed — %s", e)
            return []

        candidates = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(candidates, list):
            logger.warning(
                "ScoutInducer: response missing 'candidates' array — degrading to empty"
            )
            return []

        valid = [c for c in candidates if isinstance(c, dict) and c.get("rule_id")]
        if len(valid) != len(candidates):
            logger.warning(
                "ScoutInducer: %d of %d candidates dropped (missing rule_id or wrong type)",
                len(candidates) - len(valid),
                len(candidates),
            )
        return valid
