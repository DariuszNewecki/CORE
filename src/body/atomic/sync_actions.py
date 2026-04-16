# src/body/atomic/sync_actions.py
"""
Atomic Sync Actions - State Synchronization

Each action synchronizes one aspect of system state:
- Database knowledge graph
- Vector embeddings
- Constitutional documents

Actions are independent, composable, and auditable.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from body.atomic.registry import ActionCategory, register_action
from body.introspection.sync_service import run_sync_with_db
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.logger import getLogger


logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding helpers (mirrors repo_embedder.py module-level helpers;
# defined here so sync_actions stays within the Body layer)
# ---------------------------------------------------------------------------

_MAX_CHUNK_CHARS = 1500  # characters per semantic chunk


def _chunk_file(file_path: Path, artifact_type: str) -> list[dict[str, Any]]:
    """Chunk a file into semantic units. Returns list of {text, metadata} dicts."""
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


def _chunk_by_symbol(content: str, source: str) -> list[dict[str, Any]]:
    """Chunk Python source by top-level class and function boundaries using AST."""
    import ast as _ast

    chunks = []
    lines = content.splitlines()
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return _chunk_by_heading(content, source)

    for node in tree.body:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = node.end_lineno or (start + 30)
            text = "\n".join(lines[start:end]).strip()
            if text:
                chunks.extend(
                    _split_large(text, source, node.name, chunk_type="function")
                )
        elif isinstance(node, _ast.ClassDef):
            start = node.lineno - 1
            end = node.end_lineno or (start + 50)
            text = "\n".join(lines[start:end]).strip()
            if text:
                chunks.extend(_split_large(text, source, node.name, chunk_type="class"))

    if not chunks:
        return _chunk_whole(content, source)
    return chunks


def _chunk_by_heading(content: str, source: str) -> list[dict[str, Any]]:
    """Split markdown/YAML by headings or top-level keys."""
    chunks = []
    current_heading = "intro"
    current_text: list[str] = []

    for line in content.splitlines():
        if line.startswith("#"):
            if current_text:
                text = "\n".join(current_text).strip()
                if text:
                    chunks.extend(_split_large(text, source, current_heading))
            current_heading = line.lstrip("#").strip()
            current_text = [line]
        else:
            current_text.append(line)

    if current_text:
        text = "\n".join(current_text).strip()
        if text:
            chunks.extend(_split_large(text, source, current_heading))

    return chunks


def _chunk_by_function(content: str, source: str) -> list[dict[str, Any]]:
    """Split Python test files by test function boundaries."""
    import ast as _ast

    chunks = []
    lines = content.splitlines()
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return _chunk_by_heading(content, source)

    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                start = node.lineno - 1
                end = node.end_lineno or (start + 20)
                text = "\n".join(lines[start:end]).strip()
                if text:
                    chunks.append(
                        {
                            "text": text,
                            "metadata": {
                                "source": source,
                                "section": node.name,
                                "chunk_type": "test_function",
                            },
                        }
                    )

    if not chunks:
        return _chunk_by_heading(content, source)
    return chunks


def _chunk_whole(content: str, source: str) -> list[dict[str, Any]]:
    """Treat small files as a single chunk."""
    return _split_large(content.strip(), source, "full")


def _split_large(
    text: str,
    source: str,
    section: str,
    chunk_type: str = "section",
) -> list[dict[str, Any]]:
    """Split text that exceeds _MAX_CHUNK_CHARS into overlapping sub-chunks."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return [
            {
                "text": text,
                "metadata": {
                    "source": source,
                    "section": section,
                    "chunk_type": chunk_type,
                },
            }
        ]
    chunks = []
    step = _MAX_CHUNK_CHARS - 200  # 200-char overlap
    for i, start in enumerate(range(0, len(text), step)):
        chunk_text = text[start : start + _MAX_CHUNK_CHARS].strip()
        if chunk_text:
            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        "source": source,
                        "section": f"{section}_part{i}",
                        "chunk_type": chunk_type,
                    },
                }
            )
    return chunks


async def _embed_and_upsert(
    chunks: list[dict[str, Any]],
    collection: str,
    file_path: str,
    artifact_type: str,
    qdrant: Any,
    cognitive: Any,
) -> int:
    """Embed chunks and upsert to Qdrant. Returns number of chunks upserted."""
    from qdrant_client import models as qm

    from shared.universal import get_deterministic_id

    await qdrant.ensure_collection(collection_name=collection)

    points = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        embedding = await cognitive.get_embedding_for_code(text)
        if embedding is None:
            continue
        item_id = f"{file_path}::chunk::{i}"
        point_id = get_deterministic_id(item_id)
        payload = {
            **chunk["metadata"],
            "item_id": item_id,
            "artifact_type": artifact_type,
            "file_path": file_path,
        }
        points.append(
            qm.PointStruct(
                id=point_id,
                vector=(
                    embedding.tolist()
                    if hasattr(embedding, "tolist")
                    else list(embedding)
                ),
                payload=payload,
            )
        )

    if points:
        await qdrant.upsert_points(collection_name=collection, points=points, wait=True)

    return len(points)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@register_action(
    action_id="sync.db",
    description="Sync code symbols to PostgreSQL knowledge graph",
    category=ActionCategory.SYNC,
    policies=["rules/data/governance"],
    impact_level="moderate",
    requires_db=True,
)
@atomic_action(
    action_id="sync.db",
    intent="Atomic action for action_sync_database",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: f6789012-3456-789a-bcde-f0123456789a
async def action_sync_database(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Synchronize code symbols to PostgreSQL knowledge graph.
    """
    start = time.time()
    try:
        logger.info("Syncing symbols to database")

        if not write:
            return ActionResult(
                action_id="sync.db",
                ok=True,
                data={
                    "symbols_synced": 0,
                    "relationships_created": 0,
                    "dry_run": True,
                },
                duration_sec=time.time() - start,
            )

        async with get_session() as session:
            async with session.begin():
                result_obj = await run_sync_with_db(session)

        stats = result_obj.data

        return ActionResult(
            action_id="sync.db",
            ok=True,
            data={
                "symbols_synced": stats.get("scanned", 0),
                "inserted": stats.get("inserted", 0),
                "updated": stats.get("updated", 0),
                "deleted": stats.get("deleted", 0),
                "dry_run": False,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Database sync failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="sync.db",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="sync.vectors.code",
    description="Vectorize code symbols to Qdrant",
    category=ActionCategory.SYNC,
    policies=["rules/data/governance"],
    impact_level="moderate",
    requires_db=True,
    requires_vectors=True,
)
@atomic_action(
    action_id="sync.vectors.code",
    intent="Atomic action for action_sync_code_vectors",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: af6a56d0-b2d3-44fe-b6ea-55d6aed3768b
async def action_sync_code_vectors(
    core_context: CoreContext, write: bool = False, force: bool = False
) -> ActionResult:
    """
    Vectorize codebase artifacts to Qdrant by calling Body services directly.

    Pipeline:
      1. CrawlService.run_crawl() — walks repo, registers artifacts in
         core.repo_artifacts, extracts AST call-graph edges.
      2. ArtifactService — fetches unembedded artifacts in batches; chunking
         and Qdrant upsert handled by module-level helpers defined in this file.
    """
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry
    from shared.infrastructure.clients.qdrant_client import QdrantService

    start = time.time()

    try:
        if not write:
            logger.info(
                "Dry-run: would run CrawlService.run_crawl + ArtifactService embed loop"
            )
            return ActionResult(
                action_id="sync.vectors.code",
                ok=True,
                data={"status": "dry_run"},
                duration_sec=time.time() - start,
            )

        repo_root = BootstrapRegistry.get_repo_path()
        crawl_svc = await core_context.registry.get_crawl_service()
        artifact_svc = await core_context.registry.get_artifact_service()

        cognitive_service = core_context.cognitive_service
        if cognitive_service is None and hasattr(core_context, "registry"):
            cognitive_service = await core_context.registry.get_cognitive_service()

        # Phase 1: Crawl — register/update repo_artifacts and call-graph edges
        logger.info("sync.vectors.code: Phase 1 — CrawlService.run_crawl")
        await crawl_svc.run_crawl(repo_root, cognitive_service)

        # Phase 2: Embed — chunk and upsert all pending artifacts in batches
        logger.info("sync.vectors.code: Phase 2 — ArtifactService embed loop")
        qdrant = QdrantService()

        max_passes = 500
        for pass_num in range(1, max_passes + 1):
            pending = await artifact_svc.count_pending_artifacts()
            if pending == 0:
                logger.info(
                    "sync.vectors.code: all artifacts embedded after %d pass(es)",
                    pass_num - 1,
                )
                break
            logger.info(
                "sync.vectors.code: embedding pass %d (%d artifacts pending)",
                pass_num,
                pending,
            )
            artifacts = await artifact_svc.fetch_unembedded_artifacts(batch_size=10)
            if not artifacts:
                break

            for artifact in artifacts:
                artifact_id = artifact["id"]
                file_path_str = artifact["file_path"]
                artifact_type = artifact["artifact_type"]
                collection = artifact["qdrant_collection"]

                full_path = repo_root / file_path_str
                if not full_path.exists():
                    logger.warning("sync.vectors.code: file missing: %s", file_path_str)
                    continue

                try:
                    chunks = _chunk_file(full_path, artifact_type)
                    if not chunks:
                        await artifact_svc.mark_artifact_empty(artifact_id)
                        logger.info(
                            "sync.vectors.code: empty file skipped permanently: %s",
                            file_path_str,
                        )
                        continue

                    chunk_count = await _embed_and_upsert(
                        chunks=chunks,
                        collection=collection,
                        file_path=file_path_str,
                        artifact_type=artifact_type,
                        qdrant=qdrant,
                        cognitive=cognitive_service,
                    )

                    await artifact_svc.update_artifact_chunk_count(
                        artifact_id, chunk_count
                    )
                    logger.info(
                        "sync.vectors.code: embedded %s → %d chunks → %s",
                        file_path_str,
                        chunk_count,
                        collection,
                    )
                except Exception as exc:
                    logger.warning(
                        "sync.vectors.code: failed to embed %s: %s",
                        file_path_str,
                        exc,
                    )
        else:
            logger.warning(
                "sync.vectors.code: reached max embedding passes (%d)", max_passes
            )

        return ActionResult(
            action_id="sync.vectors.code",
            ok=True,
            data={"status": "completed", "dry_run": False},
            duration_sec=time.time() - start,
        )

    except Exception as e:
        logger.error("Code vectorization failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="sync.vectors.code",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="sync.vectors.constitution",
    description="Vectorize constitutional documents (policies, patterns)",
    category=ActionCategory.SYNC,
    policies=["rules/data/governance"],
    impact_level="safe",
    requires_vectors=True,
)
@atomic_action(
    action_id="sync.vectors.constitution",
    intent="Atomic action for action_sync_constitutional_vectors",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: b301871b-6205-4300-a76e-65d2ffa56c03
async def action_sync_constitutional_vectors(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Vectorize constitutional documents to Qdrant with smart deduplication.
    """
    start = time.time()

    try:
        logger.info("Vectorizing constitutional documents")

        if not write:
            logger.info("Dry-run: would vectorize constitutional documents")
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={"dry_run": True, "status": "skipped"},
                duration_sec=time.time() - start,
            )

        cognitive_service = core_context.cognitive_service
        if cognitive_service is None and hasattr(core_context, "registry"):
            cognitive_service = await core_context.registry.get_cognitive_service()

        if cognitive_service is None:
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={"status": "skipped", "reason": "cognitive_service_unavailable"},
                duration_sec=time.time() - start,
            )

        # Pre-flight check
        try:
            await cognitive_service.get_embedding_for_code("test")
        except Exception as e:
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={
                    "status": "skipped",
                    "reason": f"embedding_service_unavailable: {e}",
                },
                duration_sec=time.time() - start,
            )

        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )
        from shared.infrastructure.vector.vector_index_service import VectorIndexService

        embedder = CognitiveEmbedderAdapter(cognitive_service)
        adapter = ConstitutionalAdapter()

        # Policy Sync
        policy_items = adapter.policies_to_items()
        policy_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core_policies",
            embedder=embedder,
        )
        await policy_service.ensure_collection()
        policy_results = await policy_service.index_items(policy_items, batch_size=10)

        # Pattern Sync
        pattern_items = adapter.patterns_to_items()
        pattern_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core-patterns",
            embedder=embedder,
        )
        await pattern_service.ensure_collection()
        pattern_results = await pattern_service.index_items(
            pattern_items, batch_size=10
        )

        # Specs Sync
        from shared.infrastructure.vector.adapters.specs_adapter import SpecsAdapter

        specs_adapter = SpecsAdapter()
        specs_items = specs_adapter.docs_to_items()
        specs_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core_specs",
            embedder=embedder,
        )
        await specs_service.ensure_collection()
        specs_results = await specs_service.index_items(specs_items, batch_size=10)

        return ActionResult(
            action_id="sync.vectors.constitution",
            ok=True,
            data={
                "policies_count": len(policy_items),
                "policies_indexed": len(policy_results),
                "patterns_count": len(pattern_items),
                "patterns_indexed": len(pattern_results),
                "specs_count": len(specs_items),
                "specs_indexed": len(specs_results),
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Constitutional vectorization failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="sync.vectors.constitution",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
