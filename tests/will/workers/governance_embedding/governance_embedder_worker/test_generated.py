from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ID: df4c62ab-988f-417a-bc99-85e21dc0cb56
def test_governance_embedder_worker_run() -> None:
    from will.workers.governance_embedding.governance_embedder_worker import (
        GovernanceEmbedderWorker,
    )

    worker = GovernanceEmbedderWorker.__new__(GovernanceEmbedderWorker)
    worker._cognitive_service = MagicMock()
    worker._repo_root = Path("/tmp/repo")
    worker._batch_size = 50

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    claim = MagicMock()
    claim.source_path = "docs/a.md"
    claim.content_sha = "abcdef1234567890"
    claim.text = "some claim text"

    qdrant = MagicMock()
    claims_service = MagicMock()
    claims_service.is_seeded = AsyncMock(return_value=True)
    claims_service.current_keys = AsyncMock(return_value=set())
    claims_service.upsert_claims = AsyncMock(return_value=1)
    claims_service.delete_by_keys = AsyncMock(return_value=0)

    embedder = MagicMock()
    embedder.get_embeddings_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    harvester = MagicMock()
    harvester.harvest = MagicMock(return_value=[claim])

    claim_vector = MagicMock()

    service_registry = MagicMock()
    service_registry.get_qdrant_service = AsyncMock(return_value=qdrant)

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "body.services.governance_claims_service.GovernanceClaimsService",
            return_value=claims_service,
        ),
        patch(
            "body.services.governance_claims_service.ClaimVector",
            return_value=claim_vector,
        ),
        patch(
            "shared.governance.coherence_harvester.GovernanceClaimHarvester",
            return_value=harvester,
        ),
        patch(
            "shared.infrastructure.vector.cognitive_adapter.CognitiveEmbedderAdapter",
            return_value=embedder,
        ),
    ):
        asyncio.get_event_loop().run_until_complete(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    claims_service.is_seeded.assert_awaited_once()
    claims_service.current_keys.assert_awaited_once()
    claims_service.upsert_claims.assert_awaited_once()
    claims_service.delete_by_keys.assert_awaited_once_with([])
    embedder.get_embeddings_batch.assert_awaited_once_with([claim.text])
    worker.post_report.assert_awaited_once()



from will.workers.governance_embedding.governance_embedder_worker import (
    GovernanceEmbedderWorker,
)


# ID: d018572e-f96e-472f-90ef-b97be3ceb75b
async def test_GovernanceEmbedderWorker() -> None:
    worker = GovernanceEmbedderWorker(cognitive_service=MagicMock())
    worker._repo_root = MagicMock()
    worker._batch_size = 50

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    claim = MagicMock()
    claim.source_path = "governance/adr.md"
    claim.content_sha = "abc12345"
    claim.text = "Normative claim text"

    harvested_keys = {("governance/adr.md", "abc12345"): claim}

    mock_harvester = MagicMock()
    mock_harvester.harvest.return_value = [claim]

    mock_claims_service = MagicMock()
    mock_claims_service.is_seeded = AsyncMock(return_value=True)
    mock_claims_service.current_keys = AsyncMock(return_value=set())
    mock_claims_service.upsert_claims = AsyncMock(return_value=1)
    mock_claims_service.delete_by_keys = AsyncMock(return_value=0)

    mock_qdrant = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get_qdrant_service = AsyncMock(return_value=mock_qdrant)

    mock_embedder = MagicMock()
    mock_embedder.get_embeddings_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    mock_claim_vector = MagicMock()

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "body.services.governance_claims_service.GovernanceClaimsService",
            return_value=mock_claims_service,
        ),
        patch(
            "body.services.governance_claims_service.ClaimVector",
            mock_claim_vector,
        ),
        patch(
            "shared.governance.coherence_harvester.GovernanceClaimHarvester",
            return_value=mock_harvester,
        ),
        patch(
            "shared.infrastructure.vector.cognitive_adapter.CognitiveEmbedderAdapter",
            return_value=mock_embedder,
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    mock_claims_service.is_seeded.assert_awaited_once()
    mock_claims_service.current_keys.assert_awaited_once()
    mock_embedder.get_embeddings_batch.assert_awaited_once_with([claim.text])
    mock_claims_service.upsert_claims.assert_awaited_once()
    mock_claims_service.delete_by_keys.assert_awaited_once_with([])
    worker.post_report.assert_awaited_once()
