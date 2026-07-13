# src/body/services/crawl_service/main_module.py
# main_module.py
"""contains the crawl-related data-access service.

Orchestration (run_crawl pipeline) lives in orchestrator.py per ADR-042 D1
SEAM-LARGE split. CrawlService keeps a thin run_crawl wrapper for callers
that obtain the service via ServiceRegistry; the wrapper delegates to
CrawlOrchestrator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)

CORE_ROLE = "facade"  # ADR-095 D3


# ID: 5f469d78-73c8-46c8-8b6c-d0b0c5cd9ed7
class CrawlService:
    """
    Body layer service. Exposes named methods for every DB operation
    performed by RepoCrawlerWorker across crawl_runs, repo_artifacts,
    symbol_calls, artifact_symbol_links, and symbols.

    Also exposes run_crawl() as a delegating entry point for Body-layer
    callers without importing any Will worker class. The pipeline itself
    lives in CrawlOrchestrator (orchestrator.py).
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

    # ID: 3f0d0f81-6945-47d4-8422-b6de922ed7ef
    async def close_crawl_run_partial(
        self, crawl_run_id: str, stats: dict[str, int], error_summary: str
    ) -> None:
        """Mark a crawl_run as partial with stats and a failure summary. Per #179."""
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.crawl_runs SET
                        status          = 'partial',
                        files_scanned   = :files_scanned,
                        files_changed   = :files_changed,
                        symbols_linked  = :symbols_linked,
                        edges_created   = :edges_created,
                        chunks_upserted = :chunks_upserted,
                        error_message   = :error_summary,
                        finished_at     = now()
                    WHERE id = :id
                    """
                ),
                {"id": crawl_run_id, "error_summary": error_summary, **stats},
            )
            await session.commit()

    # ID: c37b42ca-7550-420c-adb6-94edfdaa3ea5
    async def close_stale_crawl_runs(self, stale_threshold_sec: int) -> int:
        """Sweep crawl_runs rows stuck in 'running' past the threshold and mark
        them 'failed'. Returns the cleaned count. Must be called BEFORE
        open_crawl_run so the current cycle's row is never swept. Per #179.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.crawl_runs
                        SET status        = 'failed',
                            error_message = 'stale-running cleanup: no completion '
                                            'within threshold',
                            finished_at   = now()
                        WHERE status = 'running'
                          AND EXTRACT(EPOCH FROM (now() - started_at))
                              > :threshold_sec
                        """
                    ),
                    {"threshold_sec": stale_threshold_sec},
                )
                return result.rowcount or 0

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
                              OR repo_artifacts.qdrant_collection
                                 IS DISTINCT FROM EXCLUDED.qdrant_collection
                            THEN 0
                            ELSE repo_artifacts.chunk_count
                        END,
                        last_crawled_at   = EXCLUDED.last_crawled_at,
                        crawl_run_id      = EXCLUDED.crawl_run_id
                    -- #786: also fire on registry-driven reclassification, not
                    -- only content drift. artifact_type / qdrant_collection are
                    -- registry facts, not content-derived — a changed glob
                    -- precedence or vector_collection must reclassify a frozen
                    -- row even when the file's bytes are unchanged. chunk_count
                    -- resets on a collection change so vectors follow the move.
                    WHERE repo_artifacts.content_hash != EXCLUDED.content_hash
                       OR repo_artifacts.artifact_type != EXCLUDED.artifact_type
                       OR repo_artifacts.qdrant_collection
                          IS DISTINCT FROM EXCLUDED.qdrant_collection
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
                              OR repo_artifacts.qdrant_collection
                                 IS DISTINCT FROM EXCLUDED.qdrant_collection
                            THEN 0
                            ELSE repo_artifacts.chunk_count
                        END,
                        last_crawled_at   = EXCLUDED.last_crawled_at,
                        crawl_run_id      = EXCLUDED.crawl_run_id
                    -- #786: also fire on registry-driven reclassification, not
                    -- only content drift. artifact_type / qdrant_collection are
                    -- registry facts, not content-derived — a changed glob
                    -- precedence or vector_collection must reclassify a frozen
                    -- row even when the file's bytes are unchanged. chunk_count
                    -- resets on a collection change so vectors follow the move.
                    WHERE repo_artifacts.content_hash != EXCLUDED.content_hash
                       OR repo_artifacts.artifact_type != EXCLUDED.artifact_type
                       OR repo_artifacts.qdrant_collection
                          IS DISTINCT FROM EXCLUDED.qdrant_collection
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

    # ID: 7d4c8e1a-3b5f-4a8c-9d2e-6c1b8e3f0a4d
    async def delete_orphan_artifacts(self, removed_paths: list[str]) -> int:
        """
        Delete core.repo_artifacts rows for files no longer present in the
        crawl pass. ADR-070 D8 writer-as-sensor reap.

        A previously-crawled file that is absent from the current pass has
        been removed from disk, moved out of crawl scope, or renamed. Its
        repo_artifacts row is now a structural orphan: RepoEmbedderWorker
        warns once per cycle, vector-store coordinates inflate, and any
        downstream query joining on file_path returns ghost evidence.
        Reaping the row in the same cycle that detected the absence is the
        writer-as-sensor pattern declared in ADR-070 D4 for this pair.

        Returns the count of orphan rows deleted.
        """
        if not removed_paths:
            return 0

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        DELETE FROM core.repo_artifacts
                        WHERE file_path = ANY(:paths)
                        """
                    ),
                    {"paths": removed_paths},
                )
                return result.rowcount or 0

    # ID: 92e7d4a3-1f5b-4c8e-a067-2d9f1b3e8c5a
    async def purge_verdicts_for_removed_files(self, removed_paths: list[str]) -> int:
        """
        Delete core.llm_gate_verdicts rows for files no longer present in the
        crawl pass. Per ADR-044 §Implementation guidance point 3 and §Consequences
        (deleted-file cleanup).

        A previously-crawled file that is absent from the current pass has either
        been removed from disk, moved out of crawl scope, or renamed. Cached
        llm_gate verdicts for that path will never be served again on a hit
        (file_content_hash for the same path will differ on any rebirth), but
        they accumulate as dead rows. Cleaning them here keeps the cache
        bounded between TTL sweeps and removes attribution to deleted files.

        Returns the count of verdict rows deleted.
        """
        if not removed_paths:
            return 0

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        DELETE FROM core.llm_gate_verdicts
                        WHERE file_path = ANY(:paths)
                        """
                    ),
                    {"paths": removed_paths},
                )
                return result.rowcount or 0

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

    # ------------------------------------------------------------------
    # Crawl orchestration (delegating entry point)
    # ------------------------------------------------------------------

    # ID: d4e5f6a7-b8c9-0123-def0-123456789012
    async def run_crawl(
        self, repo_root: Path, cognitive_service: Any = None
    ) -> dict[str, int]:
        """
        Delegate to CrawlOrchestrator. Retained on CrawlService so existing
        callers (ServiceRegistry consumers, sync.vectors_code action,
        RepoCrawlerWorker) continue to use the same public entry point.
        """
        from .orchestrator import CrawlOrchestrator

        return await CrawlOrchestrator(self).run_crawl(repo_root, cognitive_service)
