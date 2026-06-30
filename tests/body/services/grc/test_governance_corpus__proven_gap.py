"""GRC gap-analysis over the neutralized governance corpus — deterministic lane.

Runs the real `nist_800_171` catalog against the `governance_corpus` fixture
(neutralized derivatives of real governance documents) with **no LLM wired**,
so it is fully deterministic and CI-safe:

- the `regex_gate` "doc_finalized" lane fires on `enterprise-patching-policy.md`
  (which retains `TBD` / `DRAFT` placeholders) → a **proven** gap;
- the `grc_judge` judged lanes degrade honestly to `pending_ai` (no client),
  never a fabricated verdict — exercising the honest-fallback path end to end.

The judged-lane *content* (real AI verdicts) is demo-only and exercised live,
not in CI, because it requires a remote LLM.
"""

from __future__ import annotations

from pathlib import Path


from body.services.grc import GRCGapAnalysisService, load_catalog
from shared.models import EvidenceClass


_CORPUS = Path(__file__).parents[3] / "fixtures" / "grc" / "governance_corpus"


async def test_proven_gap_on_unfinalized_document() -> None:
    """The deterministic finalized-document lane proves a gap on the corpus,
    with the honest PROVEN evidence class — no LLM involved."""
    results = await GRCGapAnalysisService().run(_CORPUS, catalog=load_catalog("nist_800_171"))
    by_id = {r.requirement_id: r for r in results}

    finalized = by_id["nist_800_171.doc_finalized"]
    assert finalized.status == "gap"
    assert finalized.evidence_class is EvidenceClass.PROVEN
    assert finalized.findings, "expected at least one placeholder finding"
    # the gap is anchored on the unfinalized patching policy, not the clean docs
    assert any("patching" in f.file_path for f in finalized.findings)


async def test_judged_lane_degrades_honestly_without_llm() -> None:
    """With no LLM wired, the judged (grc_judge) lanes report pending_ai —
    never silently 'met', never a fabricated verdict (ADR-113 honesty)."""
    results = await GRCGapAnalysisService().run(_CORPUS, catalog=load_catalog("nist_800_171"))
    judged = [r for r in results if r.evidence_class is EvidenceClass.JUDGED]

    assert judged, "the NIST catalog must carry at least one judged requirement"
    assert all(r.status == "pending_ai" for r in judged)
