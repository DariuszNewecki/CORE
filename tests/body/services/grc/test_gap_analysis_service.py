"""GRC gap-analysis service — the customer-facing Scenario-4 slice.

Proves the engine runs a compliance requirements catalog (Intent) against a
document corpus (Artifact) and returns a gap report where each requirement is
honestly labelled by how its verdict was established (ADR-113):

- a deterministic check finds a real gap and labels it **proven**;
- an irreducibly-human requirement is surfaced as **attested** / needs-human,
  never silently skipped;
- the AI-judgment requirement is labelled **judged** and, with no LLM wired in
  the test, degrades honestly to `pending_ai` — never a fabricated verdict and
  never silently "met".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.services.grc import GRCGapAnalysisService
from shared.models import EvidenceClass


_CORPUS = Path(__file__).parents[3] / "fixtures" / "grc" / "corpus"


@pytest.mark.asyncio
async def test_gap_analysis_produces_labelled_trio() -> None:
    results = await GRCGapAnalysisService().run(_CORPUS)
    by_id = {r.requirement_id: r for r in results}
    assert len(results) == 3

    # PROVEN — the planted "TBD" in the encryption section is a real gap.
    proven = by_id["grc.demo.policy_is_finalized"]
    assert proven.evidence_class is EvidenceClass.PROVEN
    assert proven.status == "gap"
    assert proven.findings
    assert any("TBD" in f.message for f in proven.findings)

    # JUDGED — AI dimension, no LLM wired in the test → honest pending, not met.
    judged = by_id["grc.demo.requires_mfa_for_remote_access"]
    assert judged.evidence_class is EvidenceClass.JUDGED
    assert judged.status == "pending_ai"

    # ATTESTED — surfaced for a human, never skipped.
    attested = by_id["grc.demo.controls_appropriate_to_risk"]
    assert attested.evidence_class is EvidenceClass.ATTESTED
    assert attested.status == "needs_human"
    assert attested.findings


@pytest.mark.asyncio
async def test_clean_corpus_reports_proven_met(tmp_path: Path) -> None:
    """A finalized policy (no placeholder text) yields no proven gap."""
    doc = tmp_path / "policy.md"
    doc.write_text("# Policy\n\nAll controls are documented and finalized.\n", encoding="utf-8")
    results = await GRCGapAnalysisService().run(tmp_path)
    proven = next(r for r in results if r.requirement_id == "grc.demo.policy_is_finalized")
    assert proven.status == "met"
    assert not proven.findings
