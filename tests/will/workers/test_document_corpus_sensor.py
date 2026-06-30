# tests/will/workers/test_document_corpus_sensor.py
"""ADR-121 D2 — DocumentCorpusSensor unit tests.

Tests 1-3 from the ADR-121 verification matrix:
  1. No corpus_root → heartbeat-only, no findings.
  2. Custom catalog_root is resolved and passed through to the service.
  3. Gap-status verdicts → post_artifact_finding called once per verdict.

All three mock post_heartbeat / post_artifact_finding (blackboard writes) and
the Body service (DocumentCorpusAnalysisService) to stay in the Will layer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from shared.models.grc_verdict import (
    Applicability,
    EvidenceClass,
    RequirementStatus,
    RequirementVerdict,
)
from will.workers.document_corpus_sensor import DocumentCorpusSensor


# ── Helpers ───────────────────────────────────────────────────────────────────


# ID: 16e3345a-8bef-441e-a067-b016acb922eb
def _make_sensor(
    *,
    corpus_root: str = "",
    catalog_root: str = "",
    catalog_names: list[str] | None = None,
) -> DocumentCorpusSensor:
    """Instantiate DocumentCorpusSensor with overridden scope fields.

    Worker.__init__ reads the real .intent/workers/document_corpus_sensor.yaml
    and extracts scope values; we patch _declaration post-construction so unit
    tests don't depend on disk state.
    """
    sensor = DocumentCorpusSensor.__new__(DocumentCorpusSensor)
    sensor._declaration = {
        "mandate": {
            "scope": {
                "artifact_type": ["document_corpus"],
                "rule_namespace": "document_corpus",
            }
        },
        "config": {
            "corpus_root": corpus_root,
            "catalog_root": catalog_root,
            "catalog_names": catalog_names or [],
        },
    }
    sensor._corpus_root_str = corpus_root
    sensor._catalog_root_str = catalog_root
    sensor._catalog_names = catalog_names or []
    return sensor


# ID: 18fb106e-4ecd-4358-ab79-40efd6cac001
def _make_verdict(
    requirement_id: str,
    status: RequirementStatus,
) -> RequirementVerdict:
    return RequirementVerdict(
        requirement_id=requirement_id,
        status=status,
        applicability=Applicability.IN_SCOPE,
        evidence_class=EvidenceClass.PROVEN,
        statement="Test statement",
        rationale="Test rationale",
        evidence=[],
    )


# ── Test 1: no corpus_root → heartbeat only ───────────────────────────────────


async def test_document_corpus_sensor_no_corpus_root() -> None:
    """Test 1 (ADR-121): sensor posts heartbeat and exits when corpus_root is empty."""
    sensor = _make_sensor(corpus_root="")

    heartbeat_calls: list[object] = []
    finding_calls: list[object] = []

    async def fake_heartbeat() -> None:
        heartbeat_calls.append(True)

    async def fake_finding(**kwargs: object) -> None:  # type: ignore[misc]
        finding_calls.append(kwargs)

    sensor.post_heartbeat = fake_heartbeat  # type: ignore[method-assign]
    sensor.post_artifact_finding = fake_finding  # type: ignore[method-assign]

    await sensor.run()

    assert len(heartbeat_calls) == 1, "heartbeat must fire exactly once"
    assert len(finding_calls) == 0, "no findings when corpus_root is empty"


# ── Test 2: custom catalog_root is passed through ─────────────────────────────


async def test_document_corpus_sensor_custom_catalog_root(tmp_path: Path) -> None:
    """Test 2 (ADR-121): non-default catalog_root is resolved and forwarded to the service."""
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()
    catalog_dir = tmp_path / "my_catalogs"
    catalog_dir.mkdir()

    sensor = _make_sensor(
        corpus_root=str(corpus_dir),
        catalog_root=str(catalog_dir),
        catalog_names=["demo"],
    )

    async def fake_heartbeat() -> None:
        pass

    sensor.post_heartbeat = fake_heartbeat  # type: ignore[method-assign]
    sensor.post_artifact_finding = AsyncMock()  # type: ignore[method-assign]

    discovered = {"demo": catalog_dir / "demo.yaml"}
    rules: list[object] = []
    verdicts: list[RequirementVerdict] = []

    with (
        patch(
            "will.workers.document_corpus_sensor.DocumentCorpusSensor"
            "._discover_active_catalogs",
            return_value=["demo"],
        ),
        patch(
            "body.services.grc.gap_analysis_service.DocumentCorpusAnalysisService.run",
            new=AsyncMock(return_value=verdicts),
        ) as mock_run,
        patch(
            "body.services.grc.gap_analysis_service.load_catalog",
            return_value=rules,
        ) as mock_load,
    ):
        await sensor.run()

    mock_load.assert_called_once_with("demo", catalog_root=catalog_dir)
    mock_run.assert_called_once_with(corpus_dir, rules)


# ── Test 3: gap findings are posted ───────────────────────────────────────────


async def test_document_corpus_sensor_posts_gap_findings(tmp_path: Path) -> None:
    """Test 3 (ADR-121): two not_covered verdicts → two post_artifact_finding calls."""
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    sensor = _make_sensor(
        corpus_root=str(corpus_dir),
        catalog_names=["demo"],
    )

    async def fake_heartbeat() -> None:
        pass

    sensor.post_heartbeat = fake_heartbeat  # type: ignore[method-assign]
    finding_calls: list[dict[str, object]] = []

    async def fake_finding(**kwargs: object) -> None:  # type: ignore[misc]
        finding_calls.append(dict(kwargs))

    sensor.post_artifact_finding = fake_finding  # type: ignore[method-assign]

    gap_verdicts = [
        _make_verdict("req.001", RequirementStatus.NOT_COVERED),
        _make_verdict("req.002", RequirementStatus.NOT_COVERED),
    ]
    ok_verdict = _make_verdict("req.003", RequirementStatus.SATISFIED)

    with (
        patch(
            "will.workers.document_corpus_sensor.DocumentCorpusSensor"
            "._discover_active_catalogs",
            return_value=["demo"],
        ),
        patch(
            "body.services.grc.gap_analysis_service.DocumentCorpusAnalysisService.run",
            new=AsyncMock(return_value=[*gap_verdicts, ok_verdict]),
        ),
        patch(
            "body.services.grc.gap_analysis_service.load_catalog",
            return_value=[],
        ),
    ):
        await sensor.run()

    assert len(finding_calls) == 2, "only gap-status verdicts become findings"
    subjects = {
        f"{fc['artifact_type']}::{fc['sub_namespace']}::{fc['identity_key_value']}"
        for fc in finding_calls
    }
    assert "document_corpus::requirement::req.001" in subjects
    assert "document_corpus::requirement::req.002" in subjects
    assert all(fc["artifact_type"] == "document_corpus" for fc in finding_calls)
    assert all(fc["payload"]["status"] == RequirementStatus.NOT_COVERED.value for fc in finding_calls)
