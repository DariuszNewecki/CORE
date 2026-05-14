# src/body/services/crawl_service/orchestrator.py
"""Crawl pipeline orchestration extracted from CrawlService.

Per ADR-042 D1 SEAM-LARGE: CrawlService had two responsibilities — data-access
gateway for crawl-related tables and orchestration of the crawl pipeline.
Orchestration moves here; CrawlService keeps the data-access methods and
delegates run_crawl() to this class.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger

from .symbol_processing import (
    _CallGraphExtractor,
    _detect_layer,
    _find_symbol_references,
    _sha256,
)


if TYPE_CHECKING:
    from .main_module import CrawlService


logger = getLogger(__name__)

_CRAWL_SCOPES: list[tuple[str, str]] = [
    ("src/**/*.py", "python"),
    ("docs/**/*.md", "doc"),
    ("docs/**/*.rst", "doc"),
    ("tests/**/*.py", "test"),
    ("var/prompts/**/model.yaml", "prompt"),
    ("var/prompts/**/system.txt", "prompt"),
    ("var/prompts/**/user.txt", "prompt"),
    ("reports/**/*.yaml", "report"),
    ("reports/**/*.md", "report"),
    (".intent/**/*.yaml", "intent"),
    (".intent/**/*.json", "intent"),
    ("infra/**/*.sql", "infra"),
]

_QDRANT_COLLECTION_MAP: dict[str, str] = {
    "python": "core-code",
    "doc": "core-docs",
    "test": "core-tests",
    "prompt": "core-prompts",
    "report": "core-reports",
    "intent": "core-patterns",
    "infra": "core-docs",
}

# Stale-running janitor threshold for the crawl_runs table (#179).
# Set to 6x RepoCrawlerWorker.max_interval (600s). A run sitting in 'running'
# past this window has either been orphaned by a daemon crash or its
# terminal-status cleanup itself raised; the janitor clears it on the next
# cycle so the table stays an authoritative record of crawl outcomes.
_STALE_CRAWL_THRESHOLD_SEC = 3600

# Cap on per-file error samples recorded in a 'partial' or wholly-'failed'
# crawl_runs row. Keeps error_message bounded for storage and readability.
_MAX_ERROR_SAMPLES = 5


# ID: fc846725-fc1a-4cc2-a598-d915350b4eb0
class CrawlOrchestrator:
    """
    Drives the full crawl pipeline using a CrawlService for data access.

    Walks all declared repo scopes, registers artifacts in core.repo_artifacts,
    extracts AST call-graph edges into core.symbol_calls, and cross-references
    non-Python artifacts in core.artifact_symbol_links.
    """

    # ID: 8f66a7ef-c39b-4109-9b9b-8ba9fd65bab5
    def __init__(self, service: CrawlService) -> None:
        """
        Args:
            service: CrawlService instance providing per-table data-access
                     methods. Resolved via TYPE_CHECKING to avoid a runtime
                     import cycle with main_module.
        """
        self._service = service

    # ID: a2824aa7-72dd-4f62-a31c-74dfe42e24bc
    async def run_crawl(
        self, repo_root: Path, cognitive_service: Any = None
    ) -> dict[str, int]:
        """
        Full crawl orchestration: walk all declared repo scopes, register
        artifacts in core.repo_artifacts, extract AST call-graph edges into
        core.symbol_calls, and cross-reference non-Python artifacts in
        core.artifact_symbol_links.

        cognitive_service is accepted for interface consistency and future use;
        the current crawl is purely structural and does not invoke any LLM or
        embedding service.

        Returns stats dict with keys: files_scanned, files_changed,
        symbols_linked, edges_created, chunks_upserted, verdicts_purged.

        Terminal status (per #179): tri-state dispatch on per-file outcomes.
          - failures == 0                  → 'completed'
          - failures > 0 and successes > 0 → 'partial'
          - failures > 0 and successes == 0 → 'failed'
        """
        logger.info("CrawlOrchestrator.run_crawl: starting crawl pass")
        crawl_run_id = uuid.uuid4()
        stats: dict[str, int] = {
            "files_scanned": 0,
            "files_changed": 0,
            "symbols_linked": 0,
            "edges_created": 0,
            "chunks_upserted": 0,
            "verdicts_purged": 0,
        }

        svc = self._service

        # Stale-running janitor (#179): clear orphan rows from prior cycles
        # BEFORE opening the new run so the brand-new row is never swept.
        # Best-effort — a failure here must not block a new crawl.
        try:
            cleaned = await svc.close_stale_crawl_runs(_STALE_CRAWL_THRESHOLD_SEC)
            if cleaned:
                logger.warning(
                    "CrawlOrchestrator.run_crawl: cleaned %d stale 'running' row(s)",
                    cleaned,
                )
        except Exception as exc:
            logger.warning(
                "CrawlOrchestrator.run_crawl: stale-running cleanup failed: %s",
                exc,
            )

        await svc.open_crawl_run(str(crawl_run_id))

        # Per-file outcome tracking for tri-state status dispatch (#179)
        successes = 0
        failures = 0
        error_samples: list[str] = []

        try:
            symbol_index = await svc.load_symbol_index()
            existing_hashes = await svc.load_artifact_hashes()
            seen_paths: set[str] = set()

            for glob_pattern, artifact_type in _CRAWL_SCOPES:
                for file_path in sorted(repo_root.glob(glob_pattern)):
                    if file_path.is_symlink():
                        continue
                    rel_path = str(file_path.relative_to(repo_root))
                    seen_paths.add(rel_path)
                    stats["files_scanned"] += 1
                    try:
                        content_hash = _sha256(file_path)
                        if artifact_type == "python":
                            changed = await self._crawl_python_file(
                                file_path=file_path,
                                rel_path=rel_path,
                                content_hash=content_hash,
                                existing_hashes=existing_hashes,
                                symbol_index=symbol_index,
                                crawl_run_id=crawl_run_id,
                                stats=stats,
                            )
                        else:
                            changed = await self._crawl_artifact_file(
                                file_path=file_path,
                                rel_path=rel_path,
                                content_hash=content_hash,
                                artifact_type=artifact_type,
                                existing_hashes=existing_hashes,
                                symbol_index=symbol_index,
                                crawl_run_id=crawl_run_id,
                                stats=stats,
                            )
                        if changed:
                            stats["files_changed"] += 1
                        successes += 1
                    except Exception as exc:
                        failures += 1
                        if len(error_samples) < _MAX_ERROR_SAMPLES:
                            error_samples.append(
                                f"{rel_path} ({type(exc).__name__}: {str(exc)[:80]})"
                            )
                        logger.warning(
                            "CrawlOrchestrator.run_crawl: error processing %s: %s",
                            rel_path,
                            exc,
                        )

            # ADR-044: purge llm_gate verdicts for files that disappeared
            # from the crawl scope (deleted, moved, or renamed). Bounded by
            # previously-crawled set (existing_hashes), so we never delete
            # rows for files that were simply never crawled.
            removed_paths = sorted(set(existing_hashes.keys()) - seen_paths)
            if removed_paths:
                purged = await svc.purge_verdicts_for_removed_files(removed_paths)
                stats["verdicts_purged"] = purged
                logger.info(
                    "CrawlOrchestrator.run_crawl: purged %d verdict row(s) for "
                    "%d removed file(s)",
                    purged,
                    len(removed_paths),
                )

            # Terminal-status dispatch (#179)
            if failures == 0:
                await svc.close_crawl_run_completed(str(crawl_run_id), stats)
                terminal_status = "completed"
            elif successes == 0:
                error_msg = (
                    f"all {failures} file(s) errored. "
                    f"Samples: {'; '.join(error_samples)}"
                )
                await svc.close_crawl_run_failed(str(crawl_run_id), error_msg)
                terminal_status = "failed"
            else:
                error_summary = (
                    f"{failures} file(s) errored, {successes} succeeded. "
                    f"Samples: {'; '.join(error_samples)}"
                )
                await svc.close_crawl_run_partial(
                    str(crawl_run_id), stats, error_summary
                )
                terminal_status = "partial"
        except Exception as exc:
            # Outer-loop failure (not a per-file error). Attempt to record
            # the run as failed; if THAT raises, log both exceptions and
            # let the original propagate. The stale-running janitor on the
            # next cycle will eventually clear the orphan row.
            try:
                await svc.close_crawl_run_failed(str(crawl_run_id), str(exc))
            except Exception as cleanup_exc:
                logger.error(
                    "CrawlOrchestrator.run_crawl: close_crawl_run_failed itself "
                    "raised: %s (original error: %s) — crawl_run %s left in "
                    "'running' state, will be cleaned on next cycle",
                    cleanup_exc,
                    exc,
                    crawl_run_id,
                )
            raise

        logger.info(
            "CrawlOrchestrator.run_crawl: crawl complete (status=%s) — %s",
            terminal_status,
            stats,
        )
        return stats

    async def _crawl_python_file(
        self,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """Register a Python artifact and extract call-graph edges on change."""
        svc = self._service
        await svc.upsert_python_artifact(
            rel_path, content_hash, _QDRANT_COLLECTION_MAP["python"], str(crawl_run_id)
        )
        if existing_hashes.get(rel_path) == content_hash:
            return False

        source = file_path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning(
                "CrawlOrchestrator.run_crawl: syntax error in %s, skipping", rel_path
            )
            return True  # registered in artifacts; no call graph

        extractor = _CallGraphExtractor(
            rel_path=rel_path,
            layer=_detect_layer(rel_path),
            symbol_index=symbol_index,
            crawl_run_id=crawl_run_id,
        )
        edges = extractor.extract(tree)
        if edges:
            await svc.delete_stale_symbol_calls(rel_path, str(crawl_run_id))
            await svc.insert_symbol_calls(edges)
            stats["edges_created"] += len(edges)
        return True

    async def _crawl_artifact_file(
        self,
        file_path: Path,
        rel_path: str,
        content_hash: str,
        artifact_type: str,
        existing_hashes: dict[str, str],
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
        stats: dict[str, int],
    ) -> bool:
        """Register a non-Python artifact and cross-reference symbols on change."""
        svc = self._service
        changed = existing_hashes.get(rel_path) != content_hash
        await svc.upsert_artifact(
            rel_path,
            artifact_type,
            content_hash,
            _QDRANT_COLLECTION_MAP.get(artifact_type),
            str(crawl_run_id),
        )
        if not changed:
            return False

        artifact_id = await svc.fetch_artifact_id(rel_path)
        if artifact_id:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            links = _find_symbol_references(
                content, symbol_index, rel_path, artifact_type
            )
            await svc.insert_artifact_symbol_links(artifact_id, links)
            stats["symbols_linked"] += len(links)
        return True
