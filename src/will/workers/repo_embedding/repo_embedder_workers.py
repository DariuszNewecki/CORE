# src/will/workers/repo_embedding/repo_embedder_workers.py
# repo_embedder_workers.py
"""Contains the main worker class responsible for embedding repo artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)

from .helpers import _chunk_file, _embed_and_upsert


# ID: 1f09a2d8-0307-4172-b1b0-e3f14a918e00
class RepoEmbedderWorker(ScheduledWorker):
    """
    Sensing worker. Consumes unembedded repo_artifacts and upserts
    semantic chunks into the appropriate Qdrant collections.
    """

    declaration_name = "repo_embedder"

    def __init__(self, cognitive_service: Any = None) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        self._cognitive_service = cognitive_service
        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._batch_size: int = schedule.get("batch_size", 10)

    async def _before_loop(self) -> None:
        """Lazy-load CognitiveService if not injected (daemon context)."""
        from body.services.service_registry import service_registry

        if self._cognitive_service is None:
            self._cognitive_service = await service_registry.get_cognitive_service()

    # ID: b3c4d5e6-f7a8-9b0c-2345-678901abcdef
    async def run(self) -> None:
        """Embed a batch of unprocessed repo artifacts."""
        await self.post_heartbeat()
        from body.services.service_registry import service_registry

        logger.info("RepoEmbedderWorker: starting embedding pass")

        qdrant = await service_registry.get_qdrant_service()
        cognitive = self._cognitive_service

        stats = {"processed": 0, "chunks_total": 0, "errors": 0}

        svc = await service_registry.get_artifact_service()
        artifacts = await svc.fetch_unembedded_artifacts(self._batch_size)

        if not artifacts:
            logger.info("RepoEmbedderWorker: nothing to embed, all artifacts current")
            return

        for artifact in artifacts:
            artifact_id = artifact["id"]
            file_path = artifact["file_path"]
            artifact_type = artifact["artifact_type"]
            collection = artifact["qdrant_collection"]

            full_path = self._repo_root / file_path
            if not full_path.exists():
                logger.warning("RepoEmbedderWorker: file missing: %s", file_path)
                continue

            try:
                chunks = _chunk_file(full_path, artifact_type)
                if not chunks:
                    # Empty file — mark permanently skipped
                    await svc.mark_artifact_empty(artifact_id)
                    logger.info(
                        "RepoEmbedderWorker: empty file skipped permanently: %s",
                        file_path,
                    )
                    continue

                chunk_count = await _embed_and_upsert(
                    chunks=chunks,
                    collection=collection,
                    file_path=file_path,
                    artifact_type=artifact_type,
                    qdrant=qdrant,
                    cognitive=cognitive,
                )

                await svc.update_artifact_chunk_count(artifact_id, chunk_count)

                stats["processed"] += 1
                stats["chunks_total"] += chunk_count
                logger.info(
                    "RepoEmbedderWorker: embedded %s → %s chunks → %s",
                    file_path,
                    chunk_count,
                    collection,
                )

            except Exception as exc:
                stats["errors"] += 1
                logger.warning(
                    "RepoEmbedderWorker: failed to embed %s: %s", file_path, exc
                )

        await self.post_report(
            subject="repo.embed.complete",
            payload={
                **stats,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info("RepoEmbedderWorker: pass complete — %s", stats)
