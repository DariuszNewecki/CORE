from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: fd983dab-6dc5-43aa-9d9f-6cfb821c2ee0
async def test_SameConcernCheck_run() -> None:
    from mind.coherence.checks.sameconcern import SameConcernCheck

    repo_root = MagicMock()
    register = MagicMock()
    claims_service = MagicMock()
    claims_service.is_seeded = AsyncMock(return_value=True)

    claim_a = MagicMock()
    claim_a.text = "text a"
    claim_a.source_path = "path/a.md"
    claim_a.content_sha = "sha-a"
    claim_a.category = "cat-a"

    claim_b = MagicMock()
    claim_b.text = "text b"
    claim_b.source_path = "path/b.md"
    claim_b.content_sha = "sha-b"
    claim_b.category = "cat-b"

    hit = MagicMock()
    hit.text = "hit text"
    hit.source_path = "path/hit.md"
    hit.content_sha = "sha-hit"
    hit.category = "cat-hit"
    hit.cosine = 0.9

    claims_service.search = AsyncMock(return_value=[hit])

    verdict = MagicMock()

    claim_a_vec = [0.1, 0.2]
    claim_b_vec = [0.3, 0.4]

    mock_harvester = MagicMock()
    mock_harvester.harvest.return_value = [claim_a, claim_b]

    mock_embedder = MagicMock()
    mock_embedder.get_embeddings_batch = AsyncMock(
        return_value=[claim_a_vec, claim_b_vec]
    )

    check = SameConcernCheck(
        repo_root=repo_root,
        register=register,
        claims_service=claims_service,
        cognitive_service=MagicMock(),
        max_queries=None,
    )

    with (
        patch(
            "shared.governance.coherence_harvester.GovernanceClaimHarvester",
            return_value=mock_harvester,
        ),
        patch(
            "shared.infrastructure.vector.cognitive_adapter.CognitiveEmbedderAdapter",
            return_value=mock_embedder,
        ),
        patch(
            "mind.coherence.checks.sameconcern.judge_contradiction_pair",
            new=AsyncMock(return_value=verdict),
        ),
    ):
        result = await check.run()

    assert result == [verdict, verdict]
    mock_embedder.get_embeddings_batch.assert_awaited_once_with(["text a", "text b"])


from pathlib import Path

from mind.coherence.checks.sameconcern import SameConcernCheck


# ID: e5d139f6-5830-4dc2-ab47-9d278f748b1d
async def test_SameConcernCheck() -> None:
    repo_root = Path("/tmp/repo")
    register = MagicMock()

    claim = MagicMock()
    claim.text = "claim text"
    claim.source_path = "docs/a.md"
    claim.content_sha = "sha-a"
    claim.category = "MUST"

    hit = MagicMock()
    hit.source_path = "docs/b.md"
    hit.content_sha = "sha-b"
    hit.text = "conflicting text"
    hit.category = "MUST"
    hit.cosine = 0.80  # high_confidence tier

    claims_service = MagicMock()
    claims_service.is_seeded = AsyncMock(return_value=True)
    claims_service.search = AsyncMock(return_value=[hit])

    cognitive_service = MagicMock()

    verdict = MagicMock()

    embedder = MagicMock()
    embedder.get_embeddings_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    harvester = MagicMock()
    harvester.harvest = MagicMock(return_value=[claim])

    check = SameConcernCheck(
        repo_root=repo_root,
        register=register,
        claims_service=claims_service,
        cognitive_service=cognitive_service,
    )

    with (
        patch(
            "shared.governance.coherence_harvester.GovernanceClaimHarvester",
            return_value=harvester,
        ),
        patch(
            "shared.infrastructure.vector.cognitive_adapter.CognitiveEmbedderAdapter",
            return_value=embedder,
        ),
        patch(
            "mind.coherence.checks.sameconcern.judge_contradiction_pair",
            new=AsyncMock(return_value=verdict),
        ),
    ):
        result = await check.run()

    assert result == [verdict]
    claims_service.is_seeded.assert_awaited_once()
    embedder.get_embeddings_batch.assert_awaited_once_with([claim.text])
    claims_service.search.assert_awaited_once()
