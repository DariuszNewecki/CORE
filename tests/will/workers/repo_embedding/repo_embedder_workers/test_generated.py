from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.repo_embedding.repo_embedder_workers import RepoEmbedderWorker


# ID: 07b4bc60-5af5-47ae-98dd-cd4cea5a020f
async def test_RepoEmbedderWorker_run(tmp_path):
    worker = RepoEmbedderWorker(cognitive_service=MagicMock())
    worker._repo_root = tmp_path
    worker._batch_size = 10

    file_path = "some/file.py"
    full_path = tmp_path / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text("print('hello')\n")

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()

    qdrant = MagicMock()
    svc = MagicMock()
    svc.fetch_unembedded_artifacts = AsyncMock(
        return_value=[
            {
                "id": 1,
                "file_path": file_path,
                "artifact_type": "python",
                "qdrant_collection": "repo_python",
            }
        ]
    )
    svc.update_artifact_chunk_count = AsyncMock()
    svc.mark_artifact_empty = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_qdrant_service = AsyncMock(return_value=qdrant)
    mock_registry.get_artifact_service = AsyncMock(return_value=svc)

    chunks = [{"text": "print('hello')"}]

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "will.workers.repo_embedding.repo_embedder_workers._chunk_file",
            return_value=chunks,
        ),
        patch(
            "will.workers.repo_embedding.repo_embedder_workers._embed_and_upsert",
            new=AsyncMock(return_value=3),
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    svc.fetch_unembedded_artifacts.assert_awaited_once_with(10)
    svc.update_artifact_chunk_count.assert_awaited_once_with(1, 3)
    worker.post_report.assert_awaited_once()
    report_kwargs = worker.post_report.await_args.kwargs
    assert report_kwargs["subject"] == "repo.embed.complete"
    assert report_kwargs["payload"]["processed"] == 1
    assert report_kwargs["payload"]["chunks_total"] == 3
    assert report_kwargs["payload"]["errors"] == 0


import pytest


@pytest.mark.asyncio
# ID: 224a3a92-c579-4910-88f8-bc5ddfba8954
async def test_RepoEmbedderWorker() -> None:
    with (
        patch(
            "shared.infrastructure.bootstrap_registry.BootstrapRegistry.get_repo_path"
        ) as mock_get_repo_path,
        patch(
            "will.workers.repo_embedding.repo_embedder_workers._chunk_file"
        ) as mock_chunk_file,
        patch(
            "will.workers.repo_embedding.repo_embedder_workers._embed_and_upsert",
            new_callable=AsyncMock,
        ) as mock_embed_and_upsert,
    ):
        import pathlib

        mock_get_repo_path.return_value = pathlib.Path("/repo")

        cognitive = MagicMock()
        worker = RepoEmbedderWorker(cognitive_service=cognitive)

        worker.post_heartbeat = AsyncMock()
        worker.post_report = AsyncMock()

        chunk = MagicMock()
        mock_chunk_file.return_value = [chunk]
        mock_embed_and_upsert.return_value = 3

        artifact = {
            "id": "artifact-1",
            "file_path": "src/example.py",
            "artifact_type": "python",
            "qdrant_collection": "repo_chunks",
        }

        artifact_service = MagicMock()
        artifact_service.fetch_unembedded_artifacts = AsyncMock(return_value=[artifact])
        artifact_service.update_artifact_chunk_count = AsyncMock()
        artifact_service.mark_artifact_empty = AsyncMock()

        qdrant = MagicMock()

        mock_registry = MagicMock()
        mock_registry.get_qdrant_service = AsyncMock(return_value=qdrant)
        mock_registry.get_artifact_service = AsyncMock(return_value=artifact_service)

        fake_path = MagicMock()
        fake_path.exists.return_value = True

        with (
            patch("body.services.service_registry.service_registry", mock_registry),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await worker.run()

        artifact_service.fetch_unembedded_artifacts.assert_awaited_once()
        artifact_service.update_artifact_chunk_count.assert_awaited_once_with(
            "artifact-1", 3
        )
        mock_embed_and_upsert.assert_awaited_once()
        worker.post_report.assert_awaited_once()
        worker.post_heartbeat.assert_awaited_once()
