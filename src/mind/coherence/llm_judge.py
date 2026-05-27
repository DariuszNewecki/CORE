# src/mind/coherence/llm_judge.py
"""Shared LLM-judge logic for SAMECONCERN / R1_SCOPED contradiction verdicts.

Per ADR-073 D5 tiered cosine policy:
  - high_confidence tier: direct contradiction verdict prompt
  - ambiguous tier: prompt variant asking explicitly about adjacency-vs-contradiction

Preserves ADR-067 D3 prompt contract (constitutional_coherence_analyst role).
"""

from __future__ import annotations

import asyncio
from typing import Any

from shared.ai.response_parser import extract_json_safe
from shared.logger import getLogger

from .checks.base import CoherenceCandidate


logger = getLogger(__name__)


_LLM_CALL_TIMEOUT = 120
_USER_ID = "coherence_checker"

# Markers indicating the LLM emitted a candidate while admitting no contradiction
# exists. The prompt asks for an empty array in that case; the model sometimes
# returns a populated array whose rationale concedes alignment. Drop those.
_NO_CONTRADICTION_MARKERS = (
    "no contradiction",
    "fully aligned",
    "not contradictory",
    "no candidate is warranted",
    "no candidate is needed",
    "no direct conflict",
    "semantically equivalent",
)


_HIGH_CONFIDENCE_DESC = (
    "Same-concern contradiction check. The two normative claims below were "
    "flagged by vector similarity as addressing the same governance concern. "
    "Determine whether they make conflicting claims about that concern. "
    "Emit a candidate object only if the contradiction is real; otherwise "
    "return an empty array."
)

_AMBIGUOUS_DESC = (
    "Same-concern contradiction check (AMBIGUOUS TIER). The two normative "
    "claims below were flagged by vector similarity as POTENTIALLY related "
    "but the signal is in the ambiguous band. Distinguish carefully between:\n"
    "  (a) genuine contradiction — they make incompatible claims about the same concern\n"
    "  (b) topical adjacency — they discuss related topics without contradicting\n"
    "Only (a) warrants a candidate. Return an empty array for (b)."
)

# Applied to every judge invocation regardless of tier. Authors who write
# "Compatibility with X", "Relates to X", "Supersedes X", or "References X"
# sections are signaling deliberate reconciliation; the judge must respect
# that signal before asserting contradiction. See #474.
_COMPATIBILITY_GUARDRAIL = (
    "\n\n"
    "Before asserting a contradiction, scan each document for sections that "
    "explicitly address the other document — labels like 'Compatibility with X', "
    "'Relates to X', 'Supersedes X', 'References X', or any prose where the "
    "author reconciles the two. If either document declares the relationship "
    "(e.g., 'this ADR is compatible with X because Y'), default to no candidate "
    "unless the actual runtime behavior contradicts the declared compatibility. "
    "Authors are trusted to know their own intent; the judge catches unintended "
    "contradictions, not declared compatibility."
)

# Document headers carry an artifact-type label in parentheses (e.g.
# "DOC A (Intent · worker mandate) — ..."). The LLM has historically
# described worker YAMLs as "ADRs" in its rationale because every prior
# prompt example anchored on ADR pairs. This guardrail forces the model
# to honour the given label. See #475.
_ARTIFACT_TYPE_GUARDRAIL = (
    "\n\n"
    "Each document header carries an artifact-type label in parentheses "
    "(e.g., 'DOC A (ADR) — ...', 'DOC B (Intent · worker mandate) — ...'). "
    "When you write the claim or rationale, refer to each document by the "
    "label given. Do not call an Intent file an 'ADR'; do not call a Paper "
    "an 'ADR'; do not generalise both documents as 'these ADRs' unless both "
    "labels are 'ADR'. The labels are authoritative — your prose must match."
)


_CATEGORY_LABEL: dict[str, str] = {
    "adr": "ADR",
    "paper": "Paper",
    "northstar": "Northstar",
    "intent": "Intent file",
}

_INTENT_SUBCATEGORY: dict[str, str] = {
    "workers": "Intent · worker mandate",
    "policies": "Intent · policy",
    "rules": "Intent · rule",
    "enforcement": "Intent · enforcement config",
    "workflows": "Intent · workflow",
    "phases": "Intent · phase",
    "taxonomies": "Intent · taxonomy",
}


def _artifact_label(category: str, source_path: str) -> str:
    """Return a human-anchoring label for the (category, source_path) pair.

    Non-intent categories return their plain label. Intent files are refined
    by the first path segment under `.intent/` so the LLM sees, e.g.,
    'Intent · worker mandate' rather than the generic 'Intent file'. Unknown
    categories fall back to a lowercased label so the prompt still has *some*
    anchor instead of an empty parenthetical.
    """
    if category == "intent":
        parts = source_path.split("/")
        if len(parts) >= 2 and parts[0] == ".intent":
            subdir = parts[1]
            return _INTENT_SUBCATEGORY.get(subdir, "Intent file")
        return "Intent file"
    return _CATEGORY_LABEL.get(category, category or "Document")


# ID: 9ccc8a46-d93a-4d2b-89f0-8511915a4e46
async def judge_contradiction_pair(
    cognitive_service: Any,
    text_a: str,
    source_a: str,
    text_b: str,
    source_b: str,
    tier: str,
    relation: str = "SAMECONCERN",
    category_a: str = "",
    category_b: str = "",
) -> CoherenceCandidate | None:
    """Invoke the LLM to judge a pair of claims as contradiction or not.

    Returns a CoherenceCandidate carrying the LLM's claim+rationale if a
    contradiction is confirmed; None otherwise. All failure modes (timeout,
    parse error, schema mismatch) yield None and are logged.
    """
    from shared.ai.prompt_model import PromptModel

    base = _AMBIGUOUS_DESC if tier == "ambiguous" else _HIGH_CONFIDENCE_DESC
    description = base + _COMPATIBILITY_GUARDRAIL + _ARTIFACT_TYPE_GUARDRAIL
    label_a = _artifact_label(category_a, source_a)
    label_b = _artifact_label(category_b, source_b)
    documents_text = (
        f"=== DOC A ({label_a}) — {source_a} ===\n{text_a}\n\n"
        f"=== DOC B ({label_b}) — {source_b} ===\n{text_b}\n\n"
    )

    try:
        model = PromptModel.load("constitutional_coherence_analyst")
        client = await cognitive_service.aget_client_for_role(model.manifest.role)
        raw = await asyncio.wait_for(
            model.invoke(
                context={
                    "relation_description": description,
                    "documents_text": documents_text,
                },
                client=client,
                user_id=_USER_ID,
            ),
            timeout=_LLM_CALL_TIMEOUT,
        )
    except TimeoutError:
        logger.warning("LLM judge: timed out after %ds", _LLM_CALL_TIMEOUT)
        return None
    except Exception as exc:
        logger.warning("LLM judge: call failed: %s", exc)
        return None

    parsed = extract_json_safe(raw)
    if isinstance(parsed, dict):
        unwrapped = next((v for v in parsed.values() if isinstance(v, list)), None)
        if unwrapped is not None:
            parsed = unwrapped
    if not isinstance(parsed, list) or not parsed:
        return None

    first = parsed[0]
    if not isinstance(first, dict):
        return None
    claim = first.get("claim")
    rationale = first.get("rationale")
    if not isinstance(claim, str) or not isinstance(rationale, str):
        return None

    text = (claim + " " + rationale).lower()
    if any(marker in text for marker in _NO_CONTRADICTION_MARKERS):
        logger.debug(
            "LLM judge: dropped aligned-noise candidate (%s ↔ %s)",
            source_a,
            source_b,
        )
        return None

    return CoherenceCandidate(
        relation=relation,
        documents=[source_a, source_b],
        claim=claim,
        rationale=rationale,
    )
