# tests/body/atomic/test_document_gap_analysis_action.py
"""ADR-121 D4 — document.gap_analysis atomic action unit test.

Test 4 from the ADR-121 verification matrix:
  action_run_gap_analysis with a mocked DocumentCorpusAnalysisService returns
  an ActionResult whose data dict carries the required summary keys.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.atomic.document.gap_analysis_action import action_run_gap_analysis
from body.services.grc.catalog_resolver import CatalogPublicationUnknownError
from shared.action_types import ActionResult
from shared.governance_token import authorize_execution
from shared.models.grc_verdict import (
    Applicability,
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
        applicability=Applicability.IN_SCOPE,
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
            "body.atomic.document.gap_analysis_action.load_catalog",
            return_value=[],
        ),
        authorize_execution("document.gap_analysis"),
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


# ID: ebb30994-7d26-43e0-b46a-c4414e4e499a
async def test_run_gap_analysis_relative_corpus_root_uses_context(
    tmp_path: Path,
) -> None:
    """Relative corpus_root is resolved against core_context.file_handler.repo_path."""
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    mock_file_handler = MagicMock()
    mock_file_handler.repo_path = tmp_path
    mock_context = MagicMock()
    mock_context.file_handler = mock_file_handler

    verdicts: list[RequirementVerdict] = []

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
            "body.atomic.document.gap_analysis_action.load_catalog",
            return_value=[],
        ),
        authorize_execution("document.gap_analysis"),
    ):
        result: ActionResult = await action_run_gap_analysis(
            corpus_root="docs",
            catalog_names=["demo"],
            write=False,
            core_context=mock_context,
        )

    assert result.ok is True
    assert result.data["corpus_root"] == str(tmp_path / "docs")


# ID: bd3266f2-9c4a-4ed0-a131-bdef15a529a1
async def test_run_gap_analysis_relative_corpus_root_no_context_raises() -> None:
    """Relative corpus_root without core_context raises ValueError before any I/O."""
    with (
        authorize_execution("document.gap_analysis"),
        pytest.raises(ValueError, match="core_context"),
    ):
        await action_run_gap_analysis(
            corpus_root="relative/path",
            write=False,
            core_context=None,
        )


# ID: 3d9a5e2c-7b1e-4b6a-9c3f-5e0d2a8f4c6b
async def test_run_gap_analysis_no_catalog_names_uses_published_filter(
    tmp_path: Path,
) -> None:
    """ADR-121 D3: catalog_names=None resolves via discover_published_catalogs."""
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    with (
        patch(
            "body.atomic.document.gap_analysis_action.discover_published_catalogs",
            return_value={"nist_800_171": tmp_path / "nist_800_171.yaml"},
        ) as mock_published,
        patch(
            "body.atomic.document.gap_analysis_action.discover_catalogs"
        ) as mock_unfiltered,
        patch(
            "body.services.grc.gap_analysis_service.DocumentCorpusAnalysisService.run",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "body.atomic.document.gap_analysis_action.load_catalog",
            return_value=[],
        ),
        authorize_execution("document.gap_analysis"),
    ):
        result: ActionResult = await action_run_gap_analysis(
            corpus_root=str(corpus_dir),
            catalog_names=None,
            write=False,
        )

    mock_published.assert_called_once()
    mock_unfiltered.assert_not_called()
    assert result.ok is True
    assert "nist_800_171" in result.data["catalogs_run"]


# ID: 9c1e5a3d-2f7b-4d6a-8e0c-3b5f9a1d7e4c
async def test_run_gap_analysis_publication_unknown_returns_ok_false(
    tmp_path: Path,
) -> None:
    """ADR-121 D3: catalog_names=None + unknown publication status → ok=False
    with the specific diagnostic, not a generic "no catalogs" message and not
    a silent empty-result run."""
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    with (
        patch(
            "body.atomic.document.gap_analysis_action.discover_published_catalogs",
            side_effect=CatalogPublicationUnknownError(
                "1 catalog(s) found, but no inventory.yaml is present"
            ),
        ),
        authorize_execution("document.gap_analysis"),
    ):
        result: ActionResult = await action_run_gap_analysis(
            corpus_root=str(corpus_dir),
            catalog_names=None,
            write=False,
        )

    assert result.ok is False
    assert "inventory.yaml" in result.data["error"]
