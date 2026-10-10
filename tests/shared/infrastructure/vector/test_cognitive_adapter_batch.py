"""CognitiveEmbedderAdapter.get_embeddings_batch calls the batch method.

409f9d4e (mypy clean-up, 2026-07-03) swapped the batch call for the
single-text get_embedding_for_code(texts), which returns ONE vector: every
batch failed with "returned 768 embeddings for 32 inputs". It broke the
governance embedder worker's sync and CCC's SAMECONCERN / R1_SCOPED; seed
bootstrap only survived through its single-shot fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter


def _service(batch_result: list[list[float]]) -> MagicMock:
    service = MagicMock()
    service.get_embeddings_for_code_batch = AsyncMock(return_value=batch_result)
    # The single-text path returns one 768-dim vector, as it really does.
    service.get_embedding_for_code = AsyncMock(return_value=[0.0] * 768)
    return service


# ID: 7ef70392-4fc3-4396-8125-6898c6e6bf69
async def test_batch_uses_the_batch_method_and_stays_aligned() -> None:
    service = _service([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    adapter = CognitiveEmbedderAdapter(service)

    vectors = await adapter.get_embeddings_batch(["a", "b", "c"])

    assert vectors == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
    service.get_embeddings_for_code_batch.assert_awaited_once_with(["a", "b", "c"])
    service.get_embedding_for_code.assert_not_awaited()


# ID: ef1679db-65dc-47f5-874a-1c3aa9188ba5
async def test_batch_misalignment_still_fails_loudly() -> None:
    adapter = CognitiveEmbedderAdapter(_service([[1.0]]))

    with pytest.raises(RuntimeError, match="misalignment"):
        await adapter.get_embeddings_batch(["a", "b"])
