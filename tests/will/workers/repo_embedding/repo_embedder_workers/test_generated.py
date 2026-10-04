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
