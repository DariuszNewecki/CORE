# src/body/services/grc/internal_corpus.py
"""Internal GRC corpus ingestion and search pipeline (ADR-122).

Provides:
- ``collection_name`` — canonical Qdrant collection naming (D1).
- ``check_licence_gate`` — ingestion-time licence enforcement (D3/D5).
- ``InternalCorpusIngester`` — chunk → embed → upsert → provenance pipeline (D2/D3).
- ``InternalCorpusSearcher`` — top-K passage retrieval for judge augmentation (D4).

CONSTITUTIONAL ALIGNMENT:
- File writes go through ``FileHandler`` (governance.mutation_surface.filehandler_required).
- Settings consumed via constructor injection (architecture.boundary.settings_access).
- No async engines instantiated at import time (architecture.no_module_async_engine).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from qdrant_client.http import models as qm

from shared.logger import getLogger
from shared.time import now_iso
from shared.utils.embedding_utils import _chunk_text


if TYPE_CHECKING:
    from shared.infrastructure.clients.qdrant_client import QdrantService


logger = getLogger(__name__)

_MAX_CHUNK_CHARS = 4096
_DEFAULT_CHUNK_SIZE = 512
_DEFAULT_CHUNK_OVERLAP = 50
_INVENTORY_REL = "grc-catalogs/inventory.yaml"
_TEXT_SUFFIXES = {".txt", ".md"}

# Section IDs are dot-separated digit sequences (e.g. "3.1.1", "AC-2").
# We accept digit-only segments; alphanumeric control IDs (e.g. "AC-2") are
# stored as-is when matched, null otherwise.
_SECTION_ID_RE = re.compile(r"^[\w][\w.\-]*$")


# ID: 3870b99c-82cd-4d36-97bd-606a7ef8d929
def collection_name(framework_id: str) -> str:
    """Canonical Qdrant collection name for a framework's internal corpus (ADR-122 D1)."""
    return f"grc-internal-{framework_id}"


# ID: 171b5047-a070-47bc-8502-afbb4e5ba895
def check_licence_gate(framework_id: str, repo_root: Path) -> dict[str, Any]:
    """Enforce the ingestion-time licence gate (ADR-122 D3/D5).

    Reads ``grc-catalogs/inventory.yaml`` to locate the framework entry.
    If ``internal_use_licence: required`` is set AND
    ``grc-catalogs/internal/<framework_id>/licence.yaml`` is absent, raises
    ``ValueError`` with a clear operator message. Otherwise returns the entry
    dict (for use in the provenance record written after ingest).

    Absent ``internal_use_licence`` field = ungated (public-domain /
    official-*-reusable frameworks may be ingested unconditionally).
    """
    inventory_path = repo_root / _INVENTORY_REL
    data = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
    frameworks: dict[str, dict[str, Any]] = {
        f["id"]: f for f in (data.get("frameworks") or []) if "id" in f
    }

    entry = frameworks.get(framework_id)
    if entry is None:
        raise ValueError(
            f"Framework '{framework_id}' not found in {_INVENTORY_REL}. "
            f"Known frameworks: {sorted(frameworks)}"
        )

    if entry.get("internal_use_licence") == "required":
        licence_path = (
            repo_root / "grc-catalogs" / "internal" / framework_id / "licence.yaml"
        )
        if not licence_path.exists():
            raise ValueError(
                f"Framework '{framework_id}' requires an internal-use licence "
                f"(internal_use_licence: required in inventory.yaml). "
                f"Place grc-catalogs/internal/{framework_id}/licence.yaml to confirm "
                f"the licence is held, then re-run ingest."
            )

    return dict(entry)


# ID: 58a1e70d-8d5c-4177-abc2-5d94b9f32341
class InternalCorpusIngester:
    """Ingests a framework's text corpus into a per-framework Qdrant collection.

    Implements ADR-122 D2 (structure-aware chunking), D1 (collection naming),
    and D3 steps 3-5 (chunk/embed/upsert + provenance write).

    Receives ``QdrantService``, an embedder (``CognitiveEmbedderAdapter`` from
    the caller), and ``repo_root`` via constructor injection (Body DI contract).
    """

    def __init__(
        self,
        qdrant_service: QdrantService,
        embedding_service: Any,
        repo_root: Path,
    ) -> None:
        self._qdrant = qdrant_service
        self._embedder = embedding_service
        self._repo_root = repo_root

    # ID: 104b5f1d-7ae6-4fa7-8eef-9f263b2ee5fc
    async def ingest(
        self,
        framework_id: str,
        text_dir: Path,
        inventory_entry: dict[str, Any],
    ) -> int:
        """Chunk, embed, upsert all chunks, and write a provenance record.

        Returns the total number of chunks upserted (chunk_count recorded in
        the provenance licence.yaml).

        Raises ``ValueError`` when ``text_dir`` holds no processable files.
        """
        target_collection = collection_name(framework_id)
        files = sorted(
            f for f in text_dir.iterdir() if f.is_file() and f.suffix in _TEXT_SUFFIXES
        )
        if not files:
            raise ValueError(
                f"No text files ({', '.join(_TEXT_SUFFIXES)}) found in {text_dir}. "
                "Populate text/ with section files before ingesting."
            )

        # D2 structure-aware chunking: each section file → 1 chunk if ≤ max_chunk_chars,
        # else fall back to _chunk_text (character-based, 512/50).
        raw_chunks = self._chunk_sections(
            files, inventory_entry.get("title", framework_id)
        )
        if not raw_chunks:
            raise ValueError(f"All files in {text_dir} were unreadable or empty.")

        logger.info("Embedding %d chunk(s) for %s …", len(raw_chunks), framework_id)

        # Embed and build PointStructs
        points: list[qm.PointStruct] = []
        for chunk_text, section_id, source_ref in raw_chunks:
            vector = await self._embedder.get_embedding(chunk_text)
            points.append(
                qm.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "framework_id": framework_id,
                        "section_id": section_id,
                        "source_ref": source_ref,
                        "text": chunk_text,
                    },
                )
            )

        # Drop-and-recreate collection for clean re-ingest (ADR-122 D1/D3 step 4)
        logger.info("Recreating collection %s …", target_collection)
        await self._qdrant.drop_and_recreate_collection(target_collection)
        await self._qdrant.upsert_points(target_collection, points)
        logger.info("Upserted %d chunk(s) into %s", len(points), target_collection)

        # D3 step 5: write provenance record via FileHandler
        self._write_provenance(framework_id, text_dir, inventory_entry, len(points))
        return len(points)

    # ID: 8711006c-2daa-41a7-ba3d-744541597b98
    def _chunk_sections(
        self,
        files: list[Path],
        framework_title: str,
    ) -> list[tuple[str, str | None, str]]:
        """Chunk section files per ADR-122 D2.

        Returns a list of ``(text, section_id, source_ref)`` triples.
        ``section_id`` is derived from the file stem when it matches a word/digit
        pattern; null otherwise. Source ref is ``{title} §{section_id}`` when a
        section_id is available, else the framework title alone.
        """
        result: list[tuple[str, str | None, str]] = []
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Skipping unreadable file %s: %s", file_path, e)
                continue
            if not text:
                continue

            stem = file_path.stem
            section_id: str | None = stem if _SECTION_ID_RE.match(stem) else None
            source_ref = (
                f"{framework_title} §{section_id}" if section_id else framework_title
            )

            if len(text) <= _MAX_CHUNK_CHARS:
                result.append((text, section_id, source_ref))
            else:
                for chunk in _chunk_text(
                    text, _DEFAULT_CHUNK_SIZE, _DEFAULT_CHUNK_OVERLAP
                ):
                    result.append((chunk, section_id, source_ref))
        return result

    def _write_provenance(
        self,
        framework_id: str,
        text_dir: Path,
        inventory_entry: dict[str, Any],
        chunk_count: int,
    ) -> None:
        from body.infrastructure.storage.file_handler import FileHandler
        from shared.config import settings

        text_dir_rel = (
            str(text_dir.relative_to(self._repo_root))
            if text_dir.is_relative_to(self._repo_root)
            else str(text_dir)
        )
        provenance: dict[str, Any] = {
            "chunk_count": chunk_count,
            "collection": collection_name(framework_id),
            "embedding_model": getattr(
                self._embedder, "model", settings.LOCAL_EMBEDDING_MODEL_NAME
            ),
            "framework_id": framework_id,
            "ingested_at": now_iso(),
            "text_dir": text_dir_rel,
        }
        if "internal_use_licence" in inventory_entry:
            provenance["internal_use_licence"] = inventory_entry["internal_use_licence"]

        rel_path = f"grc-catalogs/internal/{framework_id}/licence.yaml"
        content = yaml.dump(provenance, sort_keys=True, default_flow_style=False)
        FileHandler(str(self._repo_root)).write_runtime_text(rel_path, content)
        logger.info("Wrote provenance to %s", rel_path)


# ID: 08b03555-14a6-4b5d-ac60-d1ef26c2132e
class InternalCorpusSearcher:
    """Query a framework's internal Qdrant collection for relevant passages.

    Used by the ``grc_judge`` engine for ADR-122 D4 augmentation. Degrades
    gracefully: any Qdrant or embedding error → returns an empty list (the
    judge proceeds on unaugmented baseline without raising).
    """

    def __init__(
        self,
        qdrant_service: QdrantService,
        embedding_service: Any,
    ) -> None:
        self._qdrant = qdrant_service
        self._embedder = embedding_service

    # ID: 69480492-d66d-45c0-ae0d-4425f76c26e5
    async def search(
        self,
        framework_id: str,
        query_text: str,
        top_k: int = 3,
    ) -> list[str]:
        """Return up to ``top_k`` passage texts. Empty list on absent collection or error."""
        try:
            query_vec = await self._embedder.get_embedding(query_text)
            hits = await self._qdrant.search(
                collection_name=collection_name(framework_id),
                query_vector=query_vec,
                limit=top_k,
            )
            return [
                (hit.payload or {}).get("text", "")
                for hit in hits
                if (hit.payload or {}).get("text")
            ]
        except Exception as e:
            logger.debug("Internal corpus search skipped for %s: %s", framework_id, e)
            return []
