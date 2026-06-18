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

from body.services.grc import GRCGapAnalysisService, load_catalog, load_demo_catalog
from shared.models import EvidenceClass


_CORPUS = Path(__file__).parents[3] / "fixtures" / "grc" / "corpus"


@pytest.mark.asyncio
async def test_gap_analysis_produces_labelled_trio() -> None:
    results = await GRCGapAnalysisService().run(_CORPUS, catalog=load_demo_catalog())
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
    results = await GRCGapAnalysisService().run(tmp_path, catalog=load_demo_catalog())
    proven = next(r for r in results if r.requirement_id == "grc.demo.policy_is_finalized")
    assert proven.status == "met"
    assert not proven.findings


def test_nist_catalog_loads_with_all_three_lanes() -> None:
    """The regulation-derived catalog loads as data and binds all three lanes."""
    rules = load_catalog("nist_800_171_min")
    assert len(rules) >= 5
    engines = {r.engine for r in rules}
    assert {"regex_gate", "llm_gate", "attestation_gate"} <= engines
    # attestation rules are context-level; the loader must mark them so.
    assert all(r.is_context_level for r in rules if r.engine == "attestation_gate")
    # every requirement cites a control identifier or doc-quality lane.
    assert all(r.rule_id.startswith("nist_800_171.") for r in rules)


def test_unknown_catalog_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_catalog("does_not_exist")


@pytest.mark.asyncio
async def test_nist_catalog_runs_against_corpus() -> None:
    """Default (NIST) catalog runs end-to-end: proven gap, judged, needs-human."""
    results = await GRCGapAnalysisService().run(_CORPUS)
    statuses = {r.status for r in results}
    classes = {r.evidence_class for r in results}
    # the planted TBD trips the deterministic doc-quality gate
    proven = next(r for r in results if r.requirement_id == "nist_800_171.doc_finalized")
    assert proven.evidence_class is EvidenceClass.PROVEN
    assert proven.status == "gap"
    # all three honesty lanes are represented
    assert classes == {
        EvidenceClass.PROVEN,
        EvidenceClass.JUDGED,
        EvidenceClass.ATTESTED,
    }
    assert "needs_human" in statuses
