# src/will/workers/repo_embedder.py
"""
Repo Embedder Worker — semantic self-model builder.

- Declaration:  .intent/workers/repo_embedder.yaml
- Class:        sensing
- Phase:        audit
- Schedule:     max_interval=43200s, glide_off=4320s (10% default)

Responsibilities (one per run):
  1. Query repo_artifacts for records where chunk_count = 0
     (new files or files whose hash changed since last crawl).
  2. For each artifact, load file, chunk by type, embed, upsert to Qdrant.
  3. Update repo_artifacts.chunk_count on success.
  4. Post blackboard report.

Qdrant collection routing:
  doc    → core-docs
  test   → core-tests
  prompt → core-prompts
  report → core-reports
  intent → core-patterns   (reuses existing)
  infra  → core-docs

Depends on RepoCrawlerWorker having registered files in repo_artifacts first.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_BATCH_SIZE = 10  # artifacts processed per run cycle
_MAX_CHUNK_CHARS = 1500  # characters per semantic chunk


# ID: a2b3c4d5-e6f7-8901-bcde-f12345678902
class RepoEmbedderWorker(Worker):
    """
    Sensing worker. Consumes unembedded repo_artifacts and upserts
    semantic chunks into the appropriate Qdrant collections.
    """

    declaration_name = "repo_embedder"

    def __init__(self, cognitive_service: Any = None) -> None:
        super().__init__()
        self._cognitive_service = cognitive_service
        self._repo_root: Path = settings.REPO_PATH
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 43200)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

    # ID: c4d5e6f7-a8b9-0c1d-3456-789012abcdef
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one embedding pass per
        max_interval seconds. Sanctuary calls this once on bootstrap.

        In daemon context, self-initializes CognitiveService since no
        CLI runner is present to inject it.

        Never raises — exceptions are caught, logged, and posted to Blackboard.
        """
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
            async with get_session() as init_session:
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
        logger.info("RepoEmbedderWorker: starting embedding pass")

        qdrant = QdrantService()
        cognitive = self._cognitive_service

        stats = {"processed": 0, "chunks_total": 0, "errors": 0}

        async with get_session() as session:
            # Fetch unembedded artifacts (chunk_count = 0)
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
                {"batch_size": _BATCH_SIZE},
            )
            artifacts = result.fetchall()

        if not artifacts:
            logger.info("RepoEmbedderWorker: nothing to embed, all artifacts current")
            await self.post_heartbeat()
            return

        for artifact_id, file_path, artifact_type, collection in artifacts:
            full_path = self._repo_root / file_path
            if not full_path.exists():
                logger.warning("RepoEmbedderWorker: file missing: %s", file_path)
                continue

            try:
                chunks = _chunk_file(full_path, artifact_type)
                if not chunks:
                    # Empty file — mark permanently skipped
                    async with get_session() as session:
                        await session.execute(
                            text(
                                "UPDATE core.repo_artifacts SET chunk_count = -1 WHERE id = cast(:artifact_id as uuid)"
                            ),
                            {"artifact_id": str(artifact_id)},
                        )
                        await session.commit()
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

                # Update chunk_count
                async with get_session() as session:
                    await session.execute(
                        text(
                            """
                            UPDATE core.repo_artifacts
                            SET chunk_count = :chunk_count
                            WHERE id = cast(:artifact_id as uuid)
                        """
                        ),
                        {"chunk_count": chunk_count, "artifact_id": str(artifact_id)},
                    )
                    await session.commit()

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


# ---------------------------------------------------------------------------
# Chunking strategies by artifact type
# ---------------------------------------------------------------------------


def _chunk_file(file_path: Path, artifact_type: str) -> list[dict[str, Any]]:
    """
    Chunk a file into semantic units for embedding.
    Returns list of chunk dicts: {text, metadata}.
    """
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = str(file_path)

    if artifact_type in ("doc", "report", "infra"):
        return _chunk_by_heading(content, rel_path)
    elif artifact_type == "test":
        return _chunk_by_function(content, rel_path)
    elif artifact_type == "prompt":
        return _chunk_whole(content, rel_path)
    elif artifact_type == "intent":
        return _chunk_by_heading(content, rel_path)
    else:
        return _chunk_by_heading(content, rel_path)


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


def _split_large(text: str, source: str, section: str) -> list[dict[str, Any]]:
    """Split text that exceeds _MAX_CHUNK_CHARS into overlapping sub-chunks."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return [
            {
                "text": text,
                "metadata": {
                    "source": source,
                    "section": section,
                    "chunk_type": "section",
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
                        "chunk_type": "section",
                    },
                }
            )
    return chunks


# ---------------------------------------------------------------------------
# Qdrant upsert
# ---------------------------------------------------------------------------


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
        await qdrant.upsert_points(
            collection_name=collection,
            points=points,
            wait=True,
        )

    return len(points)
