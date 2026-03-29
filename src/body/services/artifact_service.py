# src/body/services/artifact_service.py
"""
ArtifactService - Data-access layer for core.repo_artifacts (embedding lifecycle).

Covers:
  - RepoEmbedderWorker.run — fetch unembedded, mark empty, update chunk count
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: beea8b47-3e24-45cf-af38-f2624f65d3b5
class ArtifactService:
    """
    Body layer service. Exposes named methods for core.repo_artifacts
    operations used by RepoEmbedderWorker.
    """

    # ID: 5b5d1e10-9ee1-45da-971d-8c5663c445ff
    async def fetch_unembedded_artifacts(self, batch_size: int) -> list[dict[str, Any]]:
        """
        Return up to *batch_size* artifacts that have not yet been embedded
        (chunk_count = 0), ordered by most recently crawled first.
        Excludes permanently-skipped artifacts (chunk_count = -1).

        Returns list of dicts with keys: id, file_path, artifact_type,
        qdrant_collection.

        Covers:
          - RepoEmbedderWorker.run — SELECT from core.repo_artifacts WHERE chunk_count = 0
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, file_path, artifact_type, qdrant_collection
                    FROM core.repo_artifacts
                    WHERE chunk_count = 0
                      AND chunk_count != -1
                    ORDER BY last_crawled_at DESC
                    LIMIT :batch_size
                    """
                ),
                {"batch_size": batch_size},
            )
            return [
                {
                    "id": str(row[0]),
                    "file_path": row[1],
                    "artifact_type": row[2],
                    "qdrant_collection": row[3],
                }
                for row in result.fetchall()
            ]

    # ID: 5ca77ba6-4b34-46f3-a65b-29e0a29850ee
    async def mark_artifact_empty(self, artifact_id: str) -> None:
        """
        Set chunk_count = -1 to permanently skip an empty artifact.

        Covers:
          - RepoEmbedderWorker.run — UPDATE chunk_count = -1 (empty file branch)
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    "UPDATE core.repo_artifacts SET chunk_count = -1 "
                    "WHERE id = cast(:artifact_id as uuid)"
                ),
                {"artifact_id": artifact_id},
            )
            await session.commit()

    # ID: 8ed59fa4-8696-4b39-848d-582949d7248b
    async def update_artifact_chunk_count(
        self, artifact_id: str, chunk_count: int
    ) -> None:
        """
        Record the number of semantic chunks produced for an artifact
        after a successful embedding pass.

        Covers:
          - RepoEmbedderWorker.run — UPDATE core.repo_artifacts SET chunk_count = :chunk_count
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.repo_artifacts
                    SET chunk_count = :chunk_count
                    WHERE id = cast(:artifact_id as uuid)
                    """
                ),
                {"chunk_count": chunk_count, "artifact_id": artifact_id},
            )
            await session.commit()
