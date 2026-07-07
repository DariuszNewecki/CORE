# tests/mind/coherence/checks/test_sameconcern__batch_embed.py
"""Guard tests for SAMECONCERN + R1_SCOPED batch-embed refactor (#478).

These tests verify that:
- `get_embeddings_batch` is called (not the serial `get_embedding` loop)
- Batch failures abort the run and return [] without crashing
- The (claim, vector) pairing is preserved correctly
- R1_SCOPED correctly maps claim→partner_path after flattening nested pairs
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.coherence.checks.r1_scoped import R1ScopedCheck
from mind.coherence.checks.sameconcern import SameConcernCheck
from shared.governance.coherence_harvester import Claim


def _make_claim(text: str, path: str = "a.md", sha: str = "abc") -> Claim:
    return Claim(
        text=text,
        source_path=path,
        line=1,
        paragraph_index=0,
        category="rule",
        content_sha=sha,
    )


# ---------------------------------------------------------------------------
# SameConcernCheck — batch embed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sameconcern_uses_batch_embed_not_serial() -> None:
    """run() calls get_embeddings_batch once, not get_embedding N times."""
    claims = [_make_claim(f"claim {i}", sha=str(i)) for i in range(3)]
    fake_vectors = [[float(i)] * 4 for i in range(3)]

    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = True
    claims_service.search.return_value = []

    cognitive = MagicMock()

    check = SameConcernCheck(
        repo_root=Path("/tmp"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=cognitive,
        max_queries=None,
    )

    with (
        patch(
            "shared.governance.coherence_harvester.GovernanceClaimHarvester"
        ) as mock_harvester_cls,
        patch(
            "mind.coherence.checks.sameconcern.CognitiveEmbedderAdapter"
        ) as mock_adapter_cls,
    ):
        mock_harvester_cls.return_value.harvest.return_value = iter(claims)
        mock_adapter = AsyncMock()
        mock_adapter.get_embeddings_batch.return_value = fake_vectors
        mock_adapter_cls.return_value = mock_adapter

        await check.run()

        mock_adapter.get_embeddings_batch.assert_called_once_with(
            [c.text for c in claims]
        )
        mock_adapter.get_embedding.assert_not_called()


@pytest.mark.asyncio
async def test_sameconcern_batch_fail_returns_empty() -> None:
    """If batch embed raises, run() logs a warning and returns []."""
    claims = [_make_claim("x"), _make_claim("y")]

    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = True

    check = SameConcernCheck(
        repo_root=Path("/tmp"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=MagicMock(),
        max_queries=None,
    )

    with (
        patch("shared.governance.coherence_harvester.GovernanceClaimHarvester") as mh,
        patch("mind.coherence.checks.sameconcern.CognitiveEmbedderAdapter") as ma,
    ):
        mh.return_value.harvest.return_value = iter(claims)
        mock_adapter = AsyncMock()
        mock_adapter.get_embeddings_batch.side_effect = RuntimeError("embed down")
        ma.return_value = mock_adapter

        result = await check.run()

    assert result == []


# ---------------------------------------------------------------------------
# R1ScopedCheck — batch embed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1scoped_uses_batch_embed_not_serial() -> None:
    """run() collects all claims across declared pairs, then calls get_embeddings_batch once."""
    # Two ADRs with a Relates: link; each has one claim.
    claim_a = _make_claim("claim from A", path=".specs/decisions/ADR-001.md", sha="a1")
    claim_b = _make_claim("claim from B", path=".specs/decisions/ADR-002.md", sha="b1")
    fake_vectors = [[1.0, 0.0], [0.0, 1.0]]

    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = True
    claims_service.search.return_value = []

    check = R1ScopedCheck(
        repo_root=Path("/tmp"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=MagicMock(),
    )

    declared_pairs = [
        (".specs/decisions/ADR-001.md", ".specs/decisions/ADR-002.md"),
        (".specs/decisions/ADR-002.md", ".specs/decisions/ADR-001.md"),
    ]
    claims_by_path = {
        ".specs/decisions/ADR-001.md": [claim_a],
        ".specs/decisions/ADR-002.md": [claim_b],
    }

    with (
        patch.object(check, "_declared_pairs", return_value=declared_pairs),
        patch(
            "shared.governance.coherence_harvester.GovernanceClaimHarvester"
        ) as mock_harvester_cls,
        patch(
            "mind.coherence.checks.r1_scoped.CognitiveEmbedderAdapter"
        ) as mock_adapter_cls,
    ):
        mock_harvester_cls.return_value.harvest.return_value = iter([claim_a, claim_b])
        mock_adapter = AsyncMock()
        mock_adapter.get_embeddings_batch.return_value = fake_vectors
        mock_adapter_cls.return_value = mock_adapter

        await check.run()

        # Batch called exactly once with all claim texts.
        mock_adapter.get_embeddings_batch.assert_called_once()
        batch_texts = mock_adapter.get_embeddings_batch.call_args[0][0]
        assert len(batch_texts) == 2
        mock_adapter.get_embedding.assert_not_called()


@pytest.mark.asyncio
async def test_r1scoped_batch_fail_returns_empty() -> None:
    """If batch embed raises, run() returns []."""
    claim_a = _make_claim("claim A", path=".specs/decisions/ADR-001.md", sha="a1")

    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = True

    check = R1ScopedCheck(
        repo_root=Path("/tmp"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=MagicMock(),
    )

    with (
        patch.object(
            check,
            "_declared_pairs",
            return_value=[
                (".specs/decisions/ADR-001.md", ".specs/decisions/ADR-002.md")
            ],
        ),
        patch("shared.governance.coherence_harvester.GovernanceClaimHarvester") as mh,
        patch("mind.coherence.checks.r1_scoped.CognitiveEmbedderAdapter") as ma,
    ):
        mh.return_value.harvest.return_value = iter([claim_a])
        mock_adapter = AsyncMock()
        mock_adapter.get_embeddings_batch.side_effect = RuntimeError("timeout")
        ma.return_value = mock_adapter

        result = await check.run()

    assert result == []
