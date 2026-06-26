# tests/body/atomic/test_document_gap_analysis_action.py
"""ADR-121 D4 — document.run.gap_analysis atomic action unit test.

Test 4 from the ADR-121 verification matrix:
  action_run_gap_analysis with a mocked DocumentCorpusAnalysisService returns
  an ActionResult whose data dict carries the required summary keys.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from body.atomic.document.gap_analysis_action import action_run_gap_analysis
from shared.action_types import ActionResult
from shared.models.grc_verdict import (
    EvidenceClass,
    RequirementStatus,
    RequirementVerdict,
)


# ── Helper ────────────────────────────────────────────────────────────────────


# ID: ec18dc1e-ca7b-4ba4-aceb-b4d4525ec02f
def _make_verdict(req_id: str, status: RequirementStatus) -> RequirementVerdict:
    return RequirementVerdict(
        requirement_id=req_id,
        status=status,
        evidence_class=EvidenceClass.PROVEN,
        statement="",
        rationale="",
        evidence=[],
    )


# ── Test 4 ────────────────────────────────────────────────────────────────────


async def test_run_gap_analysis_action_summary(tmp_path: Path) -> None:
    """Test 4 (ADR-121): ActionResult.data carries required summary keys and correct counts."""
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    verdicts = [
        _make_verdict("r.001", RequirementStatus.SATISFIED),
        _make_verdict("r.002", RequirementStatus.NOT_COVERED),
        _make_verdict("r.003", RequirementStatus.DEFICIENT),
    ]

    with (
        patch(
            "body.atomic.document.gap_analysis_action.discover_catalogs",
            return_value={"demo": tmp_path / "demo.yaml"},
        ),
        patch(
            "body.services.grc.gap_analysis_service.DocumentCorpusAnalysisService.run",
            new=AsyncMock(return_value=verdicts),
        ),
        patch(
            "body.services.grc.gap_analysis_service.load_catalog",
            return_value=[],
        ),
    ):
        result: ActionResult = await action_run_gap_analysis(
            corpus_root=str(corpus_dir),
            catalog_names=["demo"],
            write=False,
        )

    assert result.ok is True
    data = result.data
    assert "total_requirements" in data
    assert "satisfied" in data
    assert "not_covered" in data
    assert "deficient" in data
    assert "corpus_root" in data
    assert "catalog_root" in data
    assert data["total_requirements"] == 3
    assert data["satisfied"] == 1
    assert data["not_covered"] == 1
    assert data["deficient"] == 1
    assert "demo" in data["catalogs_run"]
