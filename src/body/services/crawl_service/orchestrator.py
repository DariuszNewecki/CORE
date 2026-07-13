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

# F-41 ADR-090 D7: crawl scopes and Qdrant collection routing are derived
# from the artifact_type registry (.intent/artifact_types/*.yaml) instead
# of the previously-hardcoded module constants. crawl_scopes.yaml — which
# claimed authority for these values but was never actually loaded by the
# running code — is retired in the same change. The registry is now the
# single source of truth.


def _load_crawl_scopes_from_registry() -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Derive (crawl_scopes, qdrant_collection_map) from the registry.

    Iterates every registered artifact_type. Types with crawler_indexed:
    false (default true) are excluded — they are governed but not indexed
    for semantic search (e.g. self-governance surfaces that don't warrant
    vector embeddings yet).

    Returns:
        crawl_scopes: list of (glob_pattern, artifact_type_id) tuples in
            registry sort order.
        qdrant_collection_map: artifact_type_id → vector_collection name.
    """
    from shared.infrastructure.intent.intent_repository import (
        get_intent_repository,
    )

    repo = get_intent_repository()
    scopes: list[tuple[str, str]] = []
    collection_map: dict[str, str] = {}
    for at in repo.list_artifact_types():
        if not at.content.get("crawler_indexed", True):
            continue
        type_id = at.id
        collection_map[type_id] = at.content["vector_collection"]
        for glob in at.content["discovery"]:
            scopes.append((glob, type_id))
    return scopes, collection_map


def _glob_specificity(glob_pattern: str) -> int:
    """Rank a discovery glob's specificity by its literal (non-wildcard) prefix.

    Length of the substring before the first glob metacharacter. A more
    specific glob like ``.intent/architecture/bridges/**/*.yaml`` (literal
    prefix ``.intent/architecture/bridges/``) outranks a broader one like
    ``.intent/**/*.yaml`` (literal prefix ``.intent/``). Used by
    _resolve_file_artifact_types (#786) so a file matched by two globs is
    assigned the type of the most-specific one, deterministically, instead
    of whichever registry scope happened to be processed last.
    """
    for i, ch in enumerate(glob_pattern):
        if ch in "*?[":
            return i
    return len(glob_pattern)


def _resolve_file_artifact_types(
    repo_root: Path, crawl_scopes: list[tuple[str, str]]
) -> dict[Path, str]:
    """Assign each matched file to exactly one artifact_type — the most-specific
    matching glob's — resolving overlapping-glob ambiguity (#786).

    Returns file_path -> artifact_type. A file matched by multiple discovery
    globs (e.g. .intent/architecture/bridges/*.yaml matches both
    architecture_bridge's specific glob and intent_yaml's broad .intent/**
    glob) is resolved to the type whose glob has the longest literal prefix.
    Ties (equal specificity) keep the first-seen assignment and log a warning
    — a genuine tie is a registry ambiguity a human should resolve.
    """
    resolved: dict[Path, str] = {}
    best_spec: dict[Path, int] = {}
    for glob_pattern, artifact_type in crawl_scopes:
        spec = _glob_specificity(glob_pattern)
        for file_path in repo_root.glob(glob_pattern):
            if file_path.is_symlink() or not file_path.is_file():
                continue
            prior = best_spec.get(file_path)
            if prior is None or spec > prior:
                resolved[file_path] = artifact_type
                best_spec[file_path] = spec
            elif spec == prior and resolved[file_path] != artifact_type:
                logger.warning(
                    "CrawlOrchestrator: glob-precedence tie for %s — "
                    "%r (kept) vs %r (ignored); equal specificity. Registry "
                    "ambiguity — narrow one type's discovery glob.",
                    file_path,
                    resolved[file_path],
                    artifact_type,
                )
    return resolved


# Stale-running janitor threshold for the crawl_runs table (#179).
# Set to 6x RepoCrawlerWorker.max_interval (600s). A run sitting in 'running'
# past this window has either been orphaned by a daemon crash or its
# terminal-status cleanup itself raised; the janitor clears it on the next
# cycle so the table stays an authoritative record of crawl outcomes.
_STALE_CRAWL_THRESHOLD_SEC = 3600

# Cap on per-file error samples recorded in a 'partial' or wholly-'failed'
# crawl_runs row. Keeps error_message bounded for storage and readability.
_MAX_ERROR_SAMPLES = 5

# ADR-070 D8 safety rails. Bounds on the autonomous repo_artifacts reap
# to prevent config-drift or partial-walk catastrophe. If any guard
# trips the reap is skipped and an OPEN finding is posted for governor
# inspection (rather than running the destructive DELETE under suspect
# conditions). Hard-coded for v1 — future work may move these to
# `.intent/governance/projections.yaml` as per-pair declared bounds.
_REAP_HARD_CAP = 100  # absolute max rows reaped per cycle
_REAP_FRACTION_CAP = 0.05  # max fraction of known table reaped per cycle
_WALK_FRACTION_FLOOR = 0.5  # walked/known must exceed this (partial-walk guard)
_WALK_ABSOLUTE_FLOOR = 50  # OR walked must exceed this floor in absolute terms
# Bounded sample of candidate-to-be-reaped paths included in the
# drift-excessive finding payload for operator inspection. Keep small
# enough to fit comfortably in a CLI render and a blackboard JSONB row.
_REAP_SAMPLE_SIZE = 20


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
        stats: dict[str, Any] = {
            "files_scanned": 0,
            "files_changed": 0,
            "symbols_linked": 0,
            "edges_created": 0,
            "chunks_upserted": 0,
            "verdicts_purged": 0,
            "orphans_reaped": 0,
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

            # F-41 ADR-090 D7: scopes + collection map derived from registry.
            crawl_scopes, qdrant_collection_map = _load_crawl_scopes_from_registry()
            logger.info(
                "CrawlOrchestrator: %d crawl scopes, %d collections "
                "(from artifact_type registry)",
                len(crawl_scopes),
                len(qdrant_collection_map),
            )

            # #786: resolve overlapping-glob ambiguity BEFORE the walk — each
            # file is assigned to exactly one artifact_type (most-specific
            # matching glob) and processed once, rather than once-per-matching-
            # scope with last-scope-wins (registry-iteration-order) semantics.
            resolved_types = _resolve_file_artifact_types(repo_root, crawl_scopes)

            for file_path in sorted(resolved_types):
                artifact_type = resolved_types[file_path]
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
                            qdrant_collection_map=qdrant_collection_map,
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
                            qdrant_collection_map=qdrant_collection_map,
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

                # ADR-070 D8 writer-as-sensor reap of orphan repo_artifacts
                # rows. `removed_paths` is the (source minus projection) set
                # for the repo_artifacts/filesystem pair declared in
                # .intent/governance/projections.yaml. Reference-set bound,
                # tolerance 0: a non-empty difference is drift, reaped inline
                # — but only after the safety guards in _evaluate_reap_safety
                # confirm the diff is within declared bounds.
                guard_state = _evaluate_reap_safety(
                    removed_paths=removed_paths,
                    total_known=len(existing_hashes),
                    total_walked=len(seen_paths),
                )
                stats["coherence_guard"] = guard_state

                if guard_state["triggered"]:
                    logger.warning(
                        "CrawlOrchestrator.run_crawl: REAP SKIPPED "
                        "— safety guard tripped (%s); proposed=%d "
                        "walked=%d known=%d. Candidates left for "
                        "governor inspection (ADR-070 D8 safety rail).",
                        guard_state["trigger"],
                        guard_state["proposed_reaps"],
                        guard_state["total_walked"],
                        guard_state["total_known"],
                    )
                    # orphans_reaped stays 0; the worker reads
                    # stats["coherence_guard"] and posts an OPEN finding for
                    # governor action.
                else:
                    reaped = await svc.delete_orphan_artifacts(removed_paths)
                    stats["orphans_reaped"] = reaped
                    logger.info(
                        "CrawlOrchestrator.run_crawl: reaped %d orphan "
                        "repo_artifacts row(s) for %d removed file(s) "
                        "(ADR-070 D8)",
                        reaped,
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
        qdrant_collection_map: dict[str, str],
    ) -> bool:
        """Register a Python artifact and extract call-graph edges on change."""
        svc = self._service
        await svc.upsert_python_artifact(
            rel_path, content_hash, qdrant_collection_map["python"], str(crawl_run_id)
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
        qdrant_collection_map: dict[str, str],
    ) -> bool:
        """Register a non-Python artifact and cross-reference symbols on change."""
        svc = self._service
        changed = existing_hashes.get(rel_path) != content_hash
        await svc.upsert_artifact(
            rel_path,
            artifact_type,
            content_hash,
            qdrant_collection_map.get(artifact_type),
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


# ID: 8c1f3a5e-7d9b-4e6c-a8f2-5b3d9c1e7a4f
def _evaluate_reap_safety(
    *,
    removed_paths: list[str],
    total_known: int,
    total_walked: int,
) -> dict[str, Any]:
    """
    ADR-070 D8 safety rails — pure function that decides whether the
    proposed reap is within bounds. Returns the guard state regardless
    of outcome so the caller can record it in `stats["coherence_guard"]`
    for both the safe and the tripped paths.

    Two independent triggers, either of which trips the guard:

    - walk_too_small: the walker enumerated suspiciously few files
      compared to what the table believes exists. Bound is
      max(_WALK_ABSOLUTE_FLOOR, total_known * _WALK_FRACTION_FLOOR).
      Catches partial walks (transient I/O issues, glob-returning-empty
      on missing-directory) before they manifest as mass reaps.

    - reap_too_large: the proposed deletion count exceeds either the
      hard cap (_REAP_HARD_CAP) or the fraction cap (_REAP_FRACTION_CAP)
      of the known table size. Catches config drift (narrowed crawl
      scope) and any pathological state where the diff is implausibly
      large.

    Returns:
        {
            "triggered": bool,
            "trigger": str | None,        # comma-joined trigger names or None
            "proposed_reaps": int,
            "total_known": int,
            "total_walked": int,
            "walk_floor_required": int,
            "reap_hard_cap": int,
            "reap_fraction_cap": float,
            "sample_paths": list[str],    # bounded by _REAP_SAMPLE_SIZE
        }
    """
    proposed = len(removed_paths)
    triggers: list[str] = []

    walk_floor = max(
        _WALK_ABSOLUTE_FLOOR,
        int(total_known * _WALK_FRACTION_FLOOR),
    )
    if total_walked < walk_floor:
        triggers.append("walk_too_small")

    fraction = (proposed / total_known) if total_known > 0 else 0.0
    if proposed > _REAP_HARD_CAP or fraction > _REAP_FRACTION_CAP:
        triggers.append("reap_too_large")

    return {
        "triggered": bool(triggers),
        "trigger": ",".join(triggers) if triggers else None,
        "proposed_reaps": proposed,
        "total_known": total_known,
        "total_walked": total_walked,
        "walk_floor_required": walk_floor,
        "reap_hard_cap": _REAP_HARD_CAP,
        "reap_fraction_cap": _REAP_FRACTION_CAP,
        "sample_paths": removed_paths[:_REAP_SAMPLE_SIZE],
    }
