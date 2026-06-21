"""Tests for ADR-122 internal corpus ingestion pipeline.

Covers:
- Licence gate: ungated / gated-without-licence / gated-with-licence (D3/D5)
- Structure-aware chunking: small section → 1 chunk; large section → multiple (D2)
- Absent-collection degradation: InternalCorpusSearcher returns [] on Qdrant error (D4)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from body.services.grc.internal_corpus import (
    InternalCorpusIngester,
    InternalCorpusSearcher,
    check_licence_gate,
    collection_name,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_inventory(tmp_path: Path, extra_frameworks: list[dict] | None = None) -> Path:
    """Write a minimal inventory.yaml with nist_800_171 (ungated) and iso_27001 (gated)."""
    frameworks = [
        {
            "id": "nist_800_171",
            "title": "NIST SP 800-171 Rev. 2",
            "tier": "public",
            "ip_status": "public-domain",
        },
        {
            "id": "iso_27001",
            "title": "ISO/IEC 27001:2022",
            "tier": "licensed",
            "ip_status": "copyrighted",
            "internal_use_licence": "required",
        },
    ]
    if extra_frameworks:
        frameworks.extend(extra_frameworks)
    inventory = tmp_path / "grc-catalogs" / "inventory.yaml"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(yaml.dump({"frameworks": frameworks}), encoding="utf-8")
    return inventory


# ---------------------------------------------------------------------------
# collection_name
# ---------------------------------------------------------------------------


def test_collection_name() -> None:
    assert collection_name("nist_800_171") == "grc-internal-nist_800_171"
    assert collection_name("gdpr") == "grc-internal-gdpr"


# ---------------------------------------------------------------------------
# check_licence_gate
# ---------------------------------------------------------------------------


def test_licence_gate_ungated_framework_passes(tmp_path: Path) -> None:
    """nist_800_171 has no internal_use_licence → gate passes unconditionally."""
    _write_inventory(tmp_path)
    entry = check_licence_gate("nist_800_171", tmp_path)
    assert entry["id"] == "nist_800_171"
    assert "internal_use_licence" not in entry


def test_licence_gate_gated_without_licence_yaml_raises(tmp_path: Path) -> None:
    """iso_27001 has internal_use_licence: required; no licence.yaml → ValueError."""
    _write_inventory(tmp_path)
    with pytest.raises(ValueError, match="internal-use licence"):
        check_licence_gate("iso_27001", tmp_path)


def test_licence_gate_gated_with_licence_yaml_passes(tmp_path: Path) -> None:
    """iso_27001 with a pre-existing licence.yaml → gate passes, entry returned."""
    _write_inventory(tmp_path)
    licence_path = tmp_path / "grc-catalogs" / "internal" / "iso_27001" / "licence.yaml"
    licence_path.parent.mkdir(parents=True)
    licence_path.write_text("attested: true\n", encoding="utf-8")

    entry = check_licence_gate("iso_27001", tmp_path)
    assert entry["id"] == "iso_27001"
    assert entry["internal_use_licence"] == "required"


def test_licence_gate_unknown_framework_raises(tmp_path: Path) -> None:
    _write_inventory(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        check_licence_gate("unknown_fw", tmp_path)


# ---------------------------------------------------------------------------
# InternalCorpusIngester — chunking (unit, no Qdrant needed)
# ---------------------------------------------------------------------------


def _make_ingester(tmp_path: Path) -> InternalCorpusIngester:
    return InternalCorpusIngester(
        qdrant_service=MagicMock(),
        embedding_service=MagicMock(),
        repo_root=tmp_path,
    )


def test_chunk_sections_small_file_is_one_chunk(tmp_path: Path) -> None:
    """A section file shorter than _MAX_CHUNK_CHARS becomes exactly one chunk."""
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "3.1.1.txt").write_text("Short control text.", encoding="utf-8")

    ingester = _make_ingester(tmp_path)
    chunks = ingester._chunk_sections([text_dir / "3.1.1.txt"], "NIST 800-171")
    assert len(chunks) == 1
    text, section_id, source_ref = chunks[0]
    assert text == "Short control text."
    assert section_id == "3.1.1"
    assert "3.1.1" in source_ref


def test_chunk_sections_large_file_yields_multiple_chunks(tmp_path: Path) -> None:
    """A file exceeding _MAX_CHUNK_CHARS falls back to _chunk_text → multiple chunks."""
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    large_text = "A" * 5000
    (text_dir / "intro.txt").write_text(large_text, encoding="utf-8")

    ingester = _make_ingester(tmp_path)
    chunks = ingester._chunk_sections([text_dir / "intro.txt"], "NIST")
    assert len(chunks) > 1
    # section_id is None for non-numeric stem
    assert all(section_id is None for _, section_id, _ in chunks)


def test_chunk_sections_skips_empty_files(tmp_path: Path) -> None:
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "empty.txt").write_text("", encoding="utf-8")

    ingester = _make_ingester(tmp_path)
    chunks = ingester._chunk_sections([text_dir / "empty.txt"], "NIST")
    assert chunks == []


def test_chunk_sections_numeric_stem_becomes_section_id(tmp_path: Path) -> None:
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "AC-2.txt").write_text("Access control content.", encoding="utf-8")

    ingester = _make_ingester(tmp_path)
    chunks = ingester._chunk_sections([text_dir / "AC-2.txt"], "NIST")
    _, section_id, _ = chunks[0]
    assert section_id == "AC-2"


# ---------------------------------------------------------------------------
# InternalCorpusSearcher — absent-collection degradation (ADR-122 D4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_searcher_returns_empty_on_qdrant_error() -> None:
    """If Qdrant raises (absent collection, unreachable service), search returns []."""
    mock_qdrant = MagicMock()
    mock_qdrant.search = AsyncMock(side_effect=RuntimeError("collection not found"))

    mock_embedder = MagicMock()
    mock_embedder.get_embedding = AsyncMock(return_value=[0.1] * 768)

    searcher = InternalCorpusSearcher(
        qdrant_service=mock_qdrant,
        embedding_service=mock_embedder,
    )
    result = await searcher.search("nist_800_171", "some instruction", top_k=3)
    assert result == []


@pytest.mark.asyncio
async def test_searcher_returns_text_from_payload() -> None:
    """When Qdrant returns hits, search returns their payload text."""
    hit = MagicMock()
    hit.payload = {"text": "Control text passage.", "section_id": "3.1.1"}

    mock_qdrant = MagicMock()
    mock_qdrant.search = AsyncMock(return_value=[hit])

    mock_embedder = MagicMock()
    mock_embedder.get_embedding = AsyncMock(return_value=[0.1] * 768)

    searcher = InternalCorpusSearcher(
        qdrant_service=mock_qdrant,
        embedding_service=mock_embedder,
    )
    result = await searcher.search("nist_800_171", "instruction text", top_k=3)
    assert result == ["Control text passage."]


@pytest.mark.asyncio
async def test_searcher_skips_hits_without_text() -> None:
    """Hits with empty / missing payload text are excluded from results."""
    hit_with_text = MagicMock()
    hit_with_text.payload = {"text": "Real passage."}
    hit_no_text = MagicMock()
    hit_no_text.payload = {"text": ""}

    mock_qdrant = MagicMock()
    mock_qdrant.search = AsyncMock(return_value=[hit_with_text, hit_no_text])

    mock_embedder = MagicMock()
    mock_embedder.get_embedding = AsyncMock(return_value=[0.0] * 768)

    searcher = InternalCorpusSearcher(
        qdrant_service=mock_qdrant,
        embedding_service=mock_embedder,
    )
    result = await searcher.search("gdpr", "instruction", top_k=3)
    assert result == ["Real passage."]
