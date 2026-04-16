# src/shared/infrastructure/vector/adapters/specs_adapter.py

"""
Specs Adapter - .specs/ Markdown Vectorization

Converts human-authored specification documents under .specs/ into
VectorizableItems for semantic search.

CONSTITUTIONAL COMPLIANCE:
- Uses SpecsRepository as SSOT for all .specs/ access
- NO direct filesystem crawling or raw Path reads
- Pure orchestration: SpecsRepository → chunker → VectorizableItems
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from shared.infrastructure.specs.specs_repository import (
    SpecsRepository,
    get_specs_repository,
)
from shared.logger import getLogger
from shared.models.vector_models import VectorizableItem


logger = getLogger(__name__)


_MAX_SINGLE_CHUNK_CHARS = 1500
_COLLECTION_NAME = "core_specs"
_DOC_TYPE = "specs"
_SOURCE = "specs"


# ID: a7f3c91d-2b84-4e5a-9c1f-6d2e8a4b9c03
class SpecsAdapter:
    """
    Adapts .specs/ markdown documents into vectorizable items.

    All filesystem access is mediated by SpecsRepository; this class
    performs pure orchestration and chunking.
    """

    # ID: b8e4d2a0-3c95-4f6b-ad28-7e3f9b5ca104
    def __init__(self, specs_repository: SpecsRepository | None = None) -> None:
        """
        Args:
            specs_repository: Optional SpecsRepository instance.
                              Defaults to the singleton from get_specs_repository().
        """
        self.specs_repo = specs_repository or get_specs_repository()
        logger.debug("SpecsAdapter initialized (specs_root=%s)", self.specs_repo.root)

    # ID: c9f5e3b1-4da6-4a7c-be39-8f40ac6db215
    def docs_to_items(self, subdir: str = "") -> list[VectorizableItem]:
        """
        Convert markdown documents under .specs/ into VectorizableItems.

        Args:
            subdir: Optional subdirectory (relative to .specs/ root) to scope
                    the scan, e.g. "papers", "northstar", "requirements".
                    Empty string scans the entire .specs/ tree.

        Returns:
            List of VectorizableItem objects ready for indexing into
            the "core_specs" collection.
        """
        files = self.specs_repo.list_files(subdir=subdir, suffix=".md")
        if not files:
            logger.info(
                "No .specs/ markdown files found (subdir=%r)", subdir or "<root>"
            )
            return []

        logger.info("Processing %s spec document(s)", len(files))

        items: list[VectorizableItem] = []
        specs_root = self.specs_repo.root
        for abs_path in files:
            try:
                rel_path = abs_path.relative_to(specs_root)
            except ValueError:
                logger.warning(
                    "Skipping spec outside specs root: %s (root=%s)",
                    abs_path,
                    specs_root,
                )
                continue

            doc_id = str(rel_path).replace("\\", "/")
            try:
                text = self.specs_repo.load_text(rel_path)
            except Exception as exc:
                logger.exception("Failed to load spec %s: %s", doc_id, exc)
                continue

            file_items = self._build_items_for_file(doc_id, rel_path, text)
            items.extend(file_items)

        logger.info("Generated %s item(s) from %s spec file(s)", len(items), len(files))
        return items

    # ID: d0a6f4c2-5eb7-4b8d-cf4a-9051bd7ec326
    def _build_items_for_file(
        self, doc_id: str, rel_path: Path, text: str
    ) -> list[VectorizableItem]:
        """Chunk a single markdown document and wrap each chunk as an item."""
        body = text.strip()
        if not body:
            return []

        chunks = self._chunk_markdown(body, rel_path.stem)

        items: list[VectorizableItem] = []
        for idx, (section, content) in enumerate(chunks):
            clean = content.strip()
            if not clean:
                continue

            item_id = f"{doc_id}:{idx}"
            payload = {
                "doc_id": doc_id,
                "doc_type": _DOC_TYPE,
                "source": _SOURCE,
                "source_path": f".specs/{doc_id}",
                "section": section,
                "content_sha256": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
                "text": clean,
            }
            items.append(VectorizableItem(item_id=item_id, text=clean, payload=payload))

        return items

    # ID: e1b705d3-6fc8-4c9e-d05b-a162ce8fd437
    def _chunk_markdown(
        self, text: str, filename_section: str
    ) -> list[tuple[str, str]]:
        """
        Split markdown into (section, content) pairs.

        Small documents return a single chunk labelled with the filename stem.
        Larger documents are split on "## " headings; preamble before the first
        heading becomes its own chunk labelled with the filename stem.
        """
        if len(text) <= _MAX_SINGLE_CHUNK_CHARS:
            return [(filename_section, text)]

        sections: list[tuple[str, str]] = []
        current_section = filename_section
        current_lines: list[str] = []

        for line in text.splitlines():
            if line.startswith("## "):
                if current_lines:
                    sections.append((current_section, "\n".join(current_lines).strip()))
                current_section = line[3:].strip() or filename_section
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_section, "\n".join(current_lines).strip()))

        non_empty = [(s, c) for s, c in sections if c]
        if not non_empty:
            return [(filename_section, text)]

        return non_empty
