"""GRC gap-analysis service — the customer-facing Scenario-4 slice.

Proves the engine runs a compliance requirements catalog (Intent) against a
document corpus (Artifact) and returns a gap report where each requirement is
one corpus-level ``RequirementVerdict`` (ADR-118 D1) honestly labelled by how
its verdict was established (ADR-113):

- a deterministic check finds a real gap → DEFICIENT, evidence class PROVEN;
- an irreducibly-human requirement is surfaced as NEEDS_HUMAN / ATTESTED,
  never silently skipped;
- the AI-judgment requirement, with no LLM wired in the test, degrades
  honestly to UNAVAILABLE (never a fabricated verdict, never silently satisfied).
- document silence is NOT a gap — corpus-wide non-coverage is NOT_COVERED (D4).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from body.services.grc import GRCGapAnalysisService, load_catalog, load_demo_catalog
from shared.models import AuditFinding, AuditSeverity, EvidenceClass, RequirementStatus


_CORPUS = Path(__file__).parents[3] / "fixtures" / "grc" / "corpus"


@pytest.mark.asyncio
async def test_gap_analysis_produces_labelled_trio() -> None:
    results = await GRCGapAnalysisService().run(_CORPUS, catalog=load_demo_catalog())
    by_id = {r.requirement_id: r for r in results}
    assert len(results) == 3

    # PROVEN — the planted "TBD" is a real gap → DEFICIENT.
    proven = by_id["grc.demo.policy_is_finalized"]
    assert proven.evidence_class is EvidenceClass.PROVEN
    assert proven.status is RequirementStatus.DEFICIENT
    assert proven.evidence
    assert any("TBD" in e.cite for e in proven.evidence)

    # JUDGED — AI dimension, no LLM wired in the test → honest UNAVAILABLE.
    judged = by_id["grc.demo.requires_mfa_for_remote_access"]
    assert judged.evidence_class is EvidenceClass.JUDGED
    assert judged.status is RequirementStatus.UNAVAILABLE

    # ATTESTED — surfaced for a human, never skipped.
    attested = by_id["grc.demo.controls_appropriate_to_risk"]
    assert attested.evidence_class is EvidenceClass.ATTESTED
    assert attested.status is RequirementStatus.NEEDS_HUMAN
    assert attested.rationale


@pytest.mark.asyncio
async def test_clean_corpus_reports_proven_satisfied(tmp_path: Path) -> None:
    """A finalized policy (no placeholder text) yields no proven gap."""
    doc = tmp_path / "policy.md"
    doc.write_text("# Policy\n\nAll controls are documented and finalized.\n", encoding="utf-8")
    results = await GRCGapAnalysisService().run(tmp_path, catalog=load_demo_catalog())
    proven = next(r for r in results if r.requirement_id == "grc.demo.policy_is_finalized")
    assert proven.status is RequirementStatus.SATISFIED
    assert not proven.evidence


def test_nist_catalog_loads_with_all_three_lanes() -> None:
    """The regulation-derived catalog loads as data and binds all three lanes."""
    rules = load_catalog("nist_800_171")
    assert len(rules) >= 5
    engines = {r.engine for r in rules}
    # judged lane uses the GRC compliance judge (grc_judge), not the
    # constitutional code auditor (llm_gate).
    assert {"regex_gate", "grc_judge", "attestation_gate"} <= engines
    # attestation rules are context-level; the loader must mark them so.
    assert all(r.is_context_level for r in rules if r.engine == "attestation_gate")
    # every requirement cites a control identifier or doc-quality lane.
    assert all(r.rule_id.startswith("nist_800_171.") for r in rules)


def test_unknown_catalog_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_catalog("does_not_exist")


def test_transient_failure_classifies_unavailable_not_deficient() -> None:
    """Honesty: an enforcement failure must not be reported as DEFICIENT.

    ``_classify_deterministic`` is the deterministic path; an ENFORCEMENT_FAILURE
    finding means a verdict could not be established — UNAVAILABLE, not a gap.
    """
    from mind.logic.engines.registry import EngineRegistry
    from shared.config import settings

    EngineRegistry.initialize(settings.paths)
    service = GRCGapAnalysisService()
    rule = next(r for r in load_catalog("nist_800_171") if r.engine == "regex_gate")
    engine = EngineRegistry.get(rule.engine)

    enforcement_failure = AuditFinding(
        check_id=rule.rule_id,
        severity=AuditSeverity.BLOCK,
        message="ENFORCEMENT_FAILURE: Rule crashed.",
        file_path="none",
        context={"finding_type": "ENFORCEMENT_FAILURE"},
    )

    verdict = service._classify_deterministic(rule, [enforcement_failure], engine)
    assert verdict.status is RequirementStatus.UNAVAILABLE
    assert verdict.evidence_class is EvidenceClass.PROVEN


@pytest.mark.asyncio
async def test_judged_silence_is_not_covered_not_gap() -> None:
    """Core ADR-118 D4 invariant: a corpus where every document is silent on a
    requirement must yield NOT_COVERED, never DEFICIENT.

    Uses a mock grc_judge engine that returns coverage='silent' for every file,
    exercising the three-way aggregation logic directly.
    """
    from mind.logic.engines.base import EngineResult

    silent_result = EngineResult(
        ok=True,
        message="Document does not address this requirement (silent).",
        violations=[],
        engine_id="grc_judge",
        extra={"coverage": "silent", "reasoning": ""},
    )
    mock_engine = MagicMock()
    mock_engine.verify = AsyncMock(return_value=silent_result)

    service = GRCGapAnalysisService(llm_client=MagicMock())
    rule = next(r for r in load_demo_catalog() if r.engine == "grc_judge")

    from body.services.grc.gap_analysis_service import _CorpusContext

    context = _CorpusContext(_CORPUS)
    verdict = await service._evaluate_judged_requirement(rule, context, mock_engine)

    assert verdict.status is RequirementStatus.NOT_COVERED
    assert not verdict.evidence
    assert verdict.evidence_class is EvidenceClass.JUDGED


@pytest.mark.asyncio
async def test_nist_catalog_runs_against_corpus() -> None:
    """Default (NIST) catalog runs end-to-end: proven gap, judged, needs-human."""
    results = await GRCGapAnalysisService().run(_CORPUS)
    statuses = {r.status for r in results}
    classes = {r.evidence_class for r in results}
    # the planted TBD trips the deterministic doc-quality gate
    proven = next(r for r in results if r.requirement_id == "nist_800_171.doc_finalized")
    assert proven.evidence_class is EvidenceClass.PROVEN
    assert proven.status is RequirementStatus.DEFICIENT
    # all three honesty lanes are represented
    assert classes == {
        EvidenceClass.PROVEN,
        EvidenceClass.JUDGED,
        EvidenceClass.ATTESTED,
    }
    assert RequirementStatus.NEEDS_HUMAN in statuses


# --- catalog_resolver: residency + tier behaviour (ADR-116) -----------------


def _make_catalog(root: Path, tier: str, framework: str) -> Path:
    """Plant a minimal valid catalog.yaml under <root>/<tier>/<framework>/."""
    path = root / tier / framework / "catalog.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "catalog:\n  id: x\nrequirements: []\n", encoding="utf-8"
    )
    return path


def test_resolver_discovers_across_tiers_agnostically(tmp_path: Path) -> None:
    """discover_catalogs globs every tier; the tier is not part of the key."""
    from body.services.grc.catalog_resolver import discover_catalogs

    _make_catalog(tmp_path, "public", "nist_800_171")
    _make_catalog(tmp_path, "licensed", "gdpr")

    found = discover_catalogs(tmp_path)
    assert set(found) == {"nist_800_171", "gdpr"}
    assert found["gdpr"].parent.parent.name == "licensed"


def test_resolver_tolerates_absent_licensed_tier(tmp_path: Path) -> None:
    """A public-only corpus (no licensed/ tier) yields fewer catalogs, not an error."""
    from body.services.grc.catalog_resolver import (
        discover_catalogs,
        resolve_catalog_path,
    )

    _make_catalog(tmp_path, "public", "nist_800_171")
    assert not (tmp_path / "licensed").exists()

    found = discover_catalogs(tmp_path)
    assert set(found) == {"nist_800_171"}
    assert resolve_catalog_path("nist_800_171", tmp_path).is_file()


def test_resolver_absent_root_is_empty_not_error(tmp_path: Path) -> None:
    """An absent corpus root (public clone, credential-less CI) is empty, never raises."""
    from body.services.grc.catalog_resolver import discover_catalogs

    assert discover_catalogs(tmp_path / "does_not_exist") == {}


def test_resolver_licensed_overrides_public_same_framework(tmp_path: Path) -> None:
    """When a framework exists in both tiers, the entitled (licensed) one wins."""
    from body.services.grc.catalog_resolver import resolve_catalog_path

    _make_catalog(tmp_path, "public", "nist_800_171")
    _make_catalog(tmp_path, "licensed", "nist_800_171")
    resolved = resolve_catalog_path("nist_800_171", tmp_path)
    assert resolved.parent.parent.name == "licensed"
