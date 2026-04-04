# sensing.py
"""Contains the main worker class and chunking logic"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.workers.base import Worker


# ID: a2b3c4d5-e6f7-8901-bcde-f12345678902
class RepoEmbedderWorker(Worker):
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
        self._max_interval: int = schedule.get("max_interval", 43200)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )
        self._batch_size: int = schedule.get("batch_size", 10)

    # ID: c4d5e6f7-a8b9-0c1d-3456-789012abcdef
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one embedding pass per
        max_interval seconds. Sanctuary calls this once on bootstrap.

        In daemon context, self-initializes CognitiveService since no
        CLI runner is present to inject it.

        Never raises — exceptions are caught, logged, and posted to Blackboard.
        """
        from body.services.service_registry import service_registry
        from shared.infrastructure.clients.qdrant_client import QdrantService
        from will.orchestration.cognitive_service import CognitiveService

        logger.info(
            "RepoEmbedderWorker: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )

        # Self-initialize CognitiveService if not injected (daemon context)
        if self._cognitive_service is None:
            qdrant = QdrantService()
            cognitive = CognitiveService(
                repo_path=self._repo_root,
                qdrant_service=qdrant,
            )
            async with service_registry.session() as init_session:
                await cognitive.initialize(init_session)
            self._cognitive_service = cognitive

        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("RepoEmbedderWorker: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="repo_embedder.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("RepoEmbedderWorker: failed to post error report")

            await asyncio.sleep(self._max_interval)

    # ID: b3c4d5e6-f7a8-9b0c-2345-678901abcdef
    async def run(self) -> None:
        """Embed a batch of unprocessed repo artifacts."""
        from body.services.service_registry import service_registry

        logger.info("RepoEmbedderWorker: starting embedding pass")

        qdrant = QdrantService()
        cognitive = self._cognitive_service

        stats = {"processed": 0, "chunks_total": 0, "errors": 0}

        svc = await service_registry.get_artifact_service()
        artifacts = await svc.fetch_unembedded_artifacts(self._batch_size)

        if not artifacts:
            logger.info("RepoEmbedderWorker: nothing to embed, all artifacts current")
            await self.post_heartbeat()
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


def _chunk_file(file_path: Path, artifact_type: str) -> list[dict[str, Any]]:
    """
    Chunk a file into semantic units for embedding.
    Returns list of chunk dicts: {text, metadata}.
    """
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = str(file_path)

    if artifact_type == "python":
        return _chunk_by_symbol(content, rel_path)
    elif artifact_type in ("doc", "report", "infra"):
        return _chunk_by_heading(content, rel_path)
    elif artifact_type == "test":
        return _chunk_by_function(content, rel_path)
    elif artifact_type == "prompt":
        return _chunk_whole(content, rel_path)
    elif artifact_type == "intent":
        return _chunk_by_heading(content, rel_path)
    else:
        return _chunk_by_heading(content, rel_path)
