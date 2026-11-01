from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

from will.tools.policy_vectorizer import run_as_script


# ID: 2de94f66-6c0e-491d-a04e-7ae19d3d972a
def test_run_as_script():
    mock_result = {"policies_vectorized": 5}
    mock_cmd = AsyncMock(return_value=mock_result)

    # Patch asyncio.run with a real synchronous callable that drives the coroutine
    # to completion so AsyncMock await counters register. We keep a reference to
    # the mock so we can assert on it after the call.
    mock_run = MagicMock()

    def _fake_asyncio_run(coro):
        mock_run(coro)

        # Drive the coroutine to completion using a fresh event loop.
        async def _drive():
            return await coro

        from will.tools.policy_vectorizer import asyncio as _asyncio_mod

        # Re-entrancy: cannot use asyncio.run inside itself, so drain manually.
        loop = _asyncio_mod.new_event_loop()
        try:
            return loop.run_until_complete(_drive())
        finally:
            loop.close()

    with (
        patch(
            "will.tools.policy_vectorizer.vectorize_policies_command",
            new=mock_cmd,
        ),
        patch(
            "will.tools.policy_vectorizer.logger",
            new=MagicMock(),
        ) as mock_logger,
        patch(
            "will.tools.policy_vectorizer.asyncio.run",
            new=_fake_asyncio_run,
        ),
        patch.object(sys, "argv", ["policy_vectorizer", "--repo-root", "/tmp/repo"]),
    ):
        run_as_script()

    mock_run.assert_called_once()
    mock_cmd.assert_awaited_once()
    mock_logger.info.assert_called_once()


from pathlib import Path

from will.tools.policy_vectorizer import vectorize_policies_command


# ID: aae333dc-eba5-4d25-86b5-a4198a3700d8
async def test_vectorize_policies_command():
    repo_root = Path("/tmp/repo")
    expected_result = {"vectorized": 3, "status": "ok"}

    mock_qdrant_service = MagicMock()

    mock_cognitive_service = MagicMock()
    mock_cognitive_service.initialize = AsyncMock()

    mock_vectorizer = MagicMock()
    mock_vectorizer.vectorize_all_policies = AsyncMock(return_value=expected_result)

    with (
        patch(
            "will.tools.policy_vectorizer.QdrantService",
            return_value=mock_qdrant_service,
        ) as mock_qdrant_cls,
        patch(
            "will.tools.policy_vectorizer.CognitiveService",
            return_value=mock_cognitive_service,
        ) as mock_cognitive_cls,
        patch(
            "will.tools.policy_vectorizer.PolicyVectorizer",
            return_value=mock_vectorizer,
        ) as mock_vectorizer_cls,
    ):
        result = await vectorize_policies_command(repo_root)

    mock_qdrant_cls.assert_called_once_with()
    mock_cognitive_cls.assert_called_once_with(
        repo_path=repo_root, qdrant_service=mock_qdrant_service
    )
    mock_cognitive_service.initialize.assert_awaited_once_with()
    mock_vectorizer_cls.assert_called_once_with(
        repo_root, mock_cognitive_service, mock_qdrant_service
    )
    mock_vectorizer.vectorize_all_policies.assert_awaited_once_with()
    assert result == expected_result
