# src/body/services/crawl_service.py
"""
CrawlService - Data-access layer for repository crawl tables.

Covers all DB operations from RepoCrawlerWorker:
  - core.crawl_runs       (open / close)
  - core.repo_artifacts   (upsert python + non-python, load hashes, fetch id)
  - core.symbol_calls     (delete stale, batch insert)
  - core.artifact_symbol_links (batch insert)
  - core.symbols          (load symbol index)

Transaction note: RepoCrawlerWorker originally ran all file-level operations
inside a single session with per-file BEGIN NESTED savepoints. Each service
method here opens its own session. When migrating the worker, callers are
responsible for any required savepoint wrapping.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5f469d78-73c8-46c8-8b6c-d0b0c5cd9ed7
class CrawlService:
    """
    Body layer service. Exposes named methods for every DB operation
    performed by RepoCrawlerWorker across crawl_runs, repo_artifacts,
    symbol_calls, artifact_symbol_links, and symbols.
    """

    # ------------------------------------------------------------------
    # crawl_runs lifecycle
    # ------------------------------------------------------------------

    # ID: 42f4f41d-ada7-4662-b4b2-9c2a7ba7c800
    async def open_crawl_run(self, crawl_run_id: str) -> None:
        """
        Insert a new crawl_run record in 'running' status.

        Covers:
          - RepoCrawlerWorker.run — initial INSERT into core.crawl_runs
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.crawl_runs (id, triggered_by, status, started_at)
                    VALUES (cast(:id as uuid), 'worker', 'running', now())
                    """
                ),
                {"id": crawl_run_id},
            )
            await session.commit()

    # ID: ac48548f-ec42-442a-81df-4dd8255593c2
    async def close_crawl_run_completed(
        self, crawl_run_id: str, stats: dict[str, int]
    ) -> None:
        """
        Mark a crawl_run as completed and record final stats.

        Covers:
          - RepoCrawlerWorker.run — UPDATE core.crawl_runs SET status = 'completed'
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.crawl_runs SET
                        status          = 'completed',
                        files_scanned   = :files_scanned,
                        files_changed   = :files_changed,
                        symbols_linked  = :symbols_linked,
                        edges_created   = :edges_created,
                        chunks_upserted = :chunks_upserted,
                        finished_at     = now()
                    WHERE id = :id
                    """
                ),
                {"id": crawl_run_id, **stats},
            )
            await session.commit()

    # ID: 845ddf95-4bc1-45b7-bc28-743637178893
    async def close_crawl_run_failed(self, crawl_run_id: str, error: str) -> None:
        """
        Mark a crawl_run as failed and record the error message.

        Covers:
          - RepoCrawlerWorker.run — UPDATE core.crawl_runs SET status = 'failed'
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.crawl_runs
                    SET status = 'failed', error_message = :err, finished_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": crawl_run_id, "err": error},
            )
            await session.commit()

    # ------------------------------------------------------------------
    # repo_artifacts
    # ------------------------------------------------------------------

    # ID: 8729f486-acb0-46b1-a69a-404257979ec8
    async def upsert_python_artifact(
        self,
        file_path: str,
        content_hash: str,
        qdrant_collection: str,
        crawl_run_id: str,
    ) -> None:
        """
        Upsert a Python source file into core.repo_artifacts.
        Resets chunk_count to 0 only when the content hash changed,
        signalling RepoEmbedderWorker to re-embed the file.

        Covers:
          - RepoCrawlerWorker._process_python_file — repo_artifacts upsert
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.repo_artifacts
                        (id, file_path, artifact_type, content_hash,
                         qdrant_collection, chunk_count, last_crawled_at, crawl_run_id)
                    VALUES
                        (gen_random_uuid(), :file_path, :artifact_type, :content_hash,
                         :qdrant_collection, 0, now(), cast(:crawl_run_id as uuid))
                    ON CONFLICT (file_path) DO UPDATE SET
                        content_hash      = EXCLUDED.content_hash,
                        artifact_type     = EXCLUDED.artifact_type,
                        qdrant_collection = EXCLUDED.qdrant_collection,
                        chunk_count       = CASE
                            WHEN repo_artifacts.content_hash != EXCLUDED.content_hash
                            THEN 0
                            ELSE repo_artifacts.chunk_count
                        END,
                        last_crawled_at   = EXCLUDED.last_crawled_at,
                        crawl_run_id      = EXCLUDED.crawl_run_id
                    """
                ),
                {
                    "file_path": file_path,
                    "artifact_type": "python",
                    "content_hash": content_hash,
                    "qdrant_collection": qdrant_collection,
                    "crawl_run_id": crawl_run_id,
                },
            )
            await session.commit()

    # ID: e40bf578-0c6f-4f7f-8c00-84ffb706cb39
    async def upsert_artifact(
        self,
        file_path: str,
        artifact_type: str,
        content_hash: str,
        qdrant_collection: str | None,
        crawl_run_id: str,
    ) -> None:
        """
        Upsert a non-Python artifact into core.repo_artifacts.

        Covers:
          - RepoCrawlerWorker._process_artifact_file — repo_artifacts upsert
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.repo_artifacts
                        (id, file_path, artifact_type, content_hash,
                         qdrant_collection, last_crawled_at, crawl_run_id)
                    VALUES
                        (gen_random_uuid(), :file_path, :artifact_type, :content_hash,
                         :qdrant_collection, now(), cast(:crawl_run_id as uuid))
                    ON CONFLICT (file_path) DO UPDATE SET
                        content_hash      = EXCLUDED.content_hash,
                        artifact_type     = EXCLUDED.artifact_type,
                        qdrant_collection = EXCLUDED.qdrant_collection,
                        last_crawled_at   = EXCLUDED.last_crawled_at,
                        crawl_run_id      = EXCLUDED.crawl_run_id
                    """
                ),
                {
                    "file_path": file_path,
                    "artifact_type": artifact_type,
                    "content_hash": content_hash,
                    "qdrant_collection": qdrant_collection,
                    "crawl_run_id": crawl_run_id,
                },
            )
            await session.commit()

    # ID: f0cfa2b8-53fb-4b42-90d4-233e952a26e6
    async def fetch_artifact_id(self, file_path: str) -> str | None:
        """
        Return the UUID of a repo_artifact by file_path, or None if absent.

        Covers:
          - RepoCrawlerWorker._process_artifact_file — SELECT id FROM core.repo_artifacts
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text("SELECT id FROM core.repo_artifacts WHERE file_path = :fp"),
                {"fp": file_path},
            )
            row = result.fetchone()
            return str(row[0]) if row else None

    # ID: 588ffa06-2c09-4fa3-9eff-4ed94428ae87
    async def load_artifact_hashes(self) -> dict[str, str]:
        """
        Return file_path → content_hash for all registered artifacts.
        Used for skip-if-unchanged logic during crawl.

        Covers:
          - RepoCrawlerWorker._load_artifact_hashes
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text("SELECT file_path, content_hash FROM core.repo_artifacts")
            )
            return {row[0]: row[1] for row in result.fetchall()}

    # ------------------------------------------------------------------
    # symbol_calls
    # ------------------------------------------------------------------

    # ID: 110cc97e-1872-434f-ae33-436802b9a63f
    async def delete_stale_symbol_calls(
        self, file_path: str, crawl_run_id: str
    ) -> None:
        """
        Delete symbol_calls edges for *file_path* from any previous crawl run.

        Covers:
          - RepoCrawlerWorker._process_python_file — DELETE FROM core.symbol_calls
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM core.symbol_calls
                    WHERE file_path = :file_path
                      AND crawl_run_id != :crawl_run_id
                    """
                ),
                {"file_path": file_path, "crawl_run_id": crawl_run_id},
            )
            await session.commit()

    # ID: 92277ff6-286d-41f0-aaaf-768350e04426
    async def insert_symbol_calls(self, edges: list[dict[str, Any]]) -> None:
        """
        Batch-insert call graph edges into core.symbol_calls in a single
        transaction. Silently ignores duplicates (ON CONFLICT DO NOTHING).

        Each edge dict must contain the keys produced by _CallGraphExtractor:
        caller_id, callee_id, callee_raw, edge_kind, file_path, line_number,
        is_cross_layer, is_external, crawl_run_id.

        Covers:
          - RepoCrawlerWorker._process_python_file — INSERT INTO core.symbol_calls loop
        """
        from body.services.service_registry import ServiceRegistry

        if not edges:
            return

        async with ServiceRegistry.session() as session:
            async with session.begin():
                for edge in edges:
                    await session.execute(
                        text(
                            """
                            INSERT INTO core.symbol_calls
                                (id, caller_id, callee_id, callee_raw, edge_kind,
                                 file_path, line_number, is_cross_layer, is_external,
                                 crawl_run_id, created_at)
                            VALUES
                                (gen_random_uuid(),
                                 cast(:caller_id as uuid),
                                 cast(:callee_id as uuid),
                                 :callee_raw, :edge_kind,
                                 :file_path, :line_number,
                                 :is_cross_layer, :is_external,
                                 cast(:crawl_run_id as uuid),
                                 now())
                            ON CONFLICT DO NOTHING
                            """
                        ),
                        edge,
                    )

    # ------------------------------------------------------------------
    # artifact_symbol_links
    # ------------------------------------------------------------------

    # ID: a75c9602-8208-4608-897e-a950e8016cdf
    async def insert_artifact_symbol_links(
        self, artifact_id: str, links: list[dict[str, Any]]
    ) -> None:
        """
        Batch-insert artifact→symbol cross-reference links in a single
        transaction. Silently ignores duplicates (ON CONFLICT DO NOTHING).

        Each link dict must contain: symbol_id, link_kind, confidence, source.

        Covers:
          - RepoCrawlerWorker._process_artifact_file — INSERT INTO core.artifact_symbol_links loop
        """
        from body.services.service_registry import ServiceRegistry

        if not links:
            return

        async with ServiceRegistry.session() as session:
            async with session.begin():
                for link in links:
                    await session.execute(
                        text(
                            """
                            INSERT INTO core.artifact_symbol_links
                                (id, artifact_id, symbol_id, link_kind, confidence, source)
                            VALUES
                                (gen_random_uuid(),
                                 cast(:artifact_id as uuid),
                                 cast(:symbol_id as uuid),
                                 :link_kind, :confidence, :source)
                            ON CONFLICT DO NOTHING
                            """
                        ),
                        {"artifact_id": artifact_id, **link},
                    )

    # ------------------------------------------------------------------
    # symbols (read-only)
    # ------------------------------------------------------------------

    # ID: 1ef33e95-b0fc-425b-9152-5ba256334624
    async def load_symbol_index(self) -> dict[str, str]:
        """
        Return symbol_path → id mapping for all non-deprecated symbols.
        Used to resolve call graph callee IDs during crawl.

        Covers:
          - RepoCrawlerWorker._load_symbol_index
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    "SELECT symbol_path, id FROM core.symbols WHERE state != 'deprecated'"
                )
            )
            return {row[0]: str(row[1]) for row in result.fetchall()}
