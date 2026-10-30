from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
# ID: d9994831-c809-4efe-a527-6d73300518d1
async def test_DocumentCorpusSensor_run() -> None:
    from will.workers.document_corpus_sensor import DocumentCorpusSensor

    sensor = DocumentCorpusSensor.__new__(DocumentCorpusSensor)
    sensor._corpus_root_str = "/tmp/corpus"
    sensor._catalog_root_str = "/tmp/catalogs"
    sensor._catalog_names = []

    sensor.post_heartbeat = AsyncMock()
    sensor.post_artifact_finding = AsyncMock()

    corpus_root = MagicMock()
    catalog_root = MagicMock()
    sensor._resolve_corpus_root = MagicMock(return_value=corpus_root)
    sensor._resolve_catalog_root = MagicMock(return_value=catalog_root)
    sensor._discover_active_catalogs = MagicMock(return_value=["cat1"])

    verdict = MagicMock()
    verdict.status = MagicMock()
    verdict.requirement_id = "REQ-1"
    verdict.evidence = [MagicMock()]
    verdict.rationale = "reason"
    verdict.status.value = "deficient"
    verdict.evidence_class.value = "authoritative"

    from will.workers import document_corpus_sensor as dcs_mod

    verdict.status = (
        dcs_mod.RequirementStatus.DEFICIENT
        if hasattr(dcs_mod, "RequirementStatus")
        else verdict.status
    )

    mock_service = MagicMock()
    mock_service.run = AsyncMock(return_value=[verdict])

    with (
        patch(
            "body.services.grc.gap_analysis_service.DocumentCorpusAnalysisService",
            return_value=mock_service,
        ),
        patch(
            "body.services.grc.gap_analysis_service.load_catalog",
            return_value=MagicMock(),
        ),
    ):
        await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    sensor._discover_active_catalogs.assert_called_once_with(catalog_root)
    mock_service.run.assert_awaited_once()

    if verdict.status in dcs_mod._GAP_STATUSES:
        sensor.post_artifact_finding.assert_awaited_once()


import asyncio

from will.workers.document_corpus_sensor import DocumentCorpusSensor


# ID: 0a5ca4b3-5e6c-4ae4-96ff-692c24b56b37
def test_DocumentCorpusSensor():
    worker = DocumentCorpusSensor()
    worker._corpus_root_str = ""
    worker._catalog_root_str = ""
    worker._catalog_names = []

    with patch.object(worker, "post_heartbeat", new=AsyncMock()) as mock_hb:
        asyncio.run(worker.run())

    mock_hb.assert_awaited_once()
