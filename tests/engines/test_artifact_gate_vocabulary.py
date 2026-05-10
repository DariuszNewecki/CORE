"""Fixture tests for ArtifactGateEngine vocabulary check_types.

Each test builds a minimal repo under tmp_path (.intent/, .specs/) with a
canonical Markdown section plus a JSON projection, then exercises the engine
end-to-end via verify(). Pure file-system checks — no DB fixtures.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from mind.logic.engines.artifact_gate import ArtifactGateEngine
from shared.infrastructure.intent.vocabulary_projection import (
    locate_canonical_section,
)


def _real_meta_dir() -> Path:
    """Locate the live .intent/META/ directory by walking up from this test."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / ".intent" / "META"
        if (cand / "vocabulary.schema.json").is_file():
            return cand
    raise RuntimeError("Could not locate .intent/META/ from test path")


def _hash_canonical(md: str) -> str:
    rng = locate_canonical_section(md)
    if rng is None:
        return ""
    start, end = rng
    section = "\n".join(md.splitlines()[start:end])
    return hashlib.sha256(section.encode("utf-8")).hexdigest()


def _md(rows: list[tuple[str, str, str, str]]) -> str:
    """Render a minimal CORE-Vocabulary.md with a canonical section."""
    body = "\n".join(f"| {t} | {d} | {n} | {p} |" for t, d, n, p in rows)
    return (
        "# CORE Vocabulary\n\n"
        "## Canonical Vocabulary (Machine Section)\n\n"
        "| term | definition | not | authoritative_paper |\n"
        "|------|------------|-----|---------------------|\n"
        f"{body}\n\n"
        "---\n"
    )


def _vocab_json(terms: list[dict], source_hash: str) -> dict:
    """Build a vocabulary.json instance that satisfies vocabulary.schema.json.

    Top-level requires `$schema`, `kind`, `metadata`, `terms`. Other
    metadata fields (id, title, version, authority, status) may also be
    schema-required — populated with sensible defaults to match the live
    vocabulary.json shape.
    """
    return {
        "$schema": "META/vocabulary.schema.json",
        "kind": "vocabulary",
        "metadata": {
            "id": "core.vocabulary",
            "title": "Test Vocabulary",
            "version": "1.0.0",
            "authority": "meta",
            "status": "active",
            "source_hash": source_hash,
            "generated_at": "2026-05-10T00:00:00Z",
            "generator_version": "test-fixture",
        },
        "terms": terms,
    }


def _build_repo(
    tmp_path: Path,
    canonical_md: str,
    vocab: dict,
) -> Path:
    intent_meta = tmp_path / ".intent" / "META"
    intent_meta.mkdir(parents=True)
    specs_papers = tmp_path / ".specs" / "papers"
    specs_papers.mkdir(parents=True)
    real_meta = _real_meta_dir()
    # Copy the schema and any sibling files it $refs (enums.json) so
    # jsonschema's RefResolver can satisfy local references inside tmp_path.
    shutil.copy(
        real_meta / "vocabulary.schema.json", intent_meta / "vocabulary.schema.json"
    )
    shutil.copy(real_meta / "enums.json", intent_meta / "enums.json")
    (intent_meta / "vocabulary.json").write_text(
        json.dumps(vocab, indent=2), encoding="utf-8"
    )
    (specs_papers / "CORE-Vocabulary.md").write_text(canonical_md, encoding="utf-8")
    return tmp_path


def _verify(repo: Path, check_type: str):
    engine = ArtifactGateEngine()
    file_path = (repo / ".intent" / "META" / "vocabulary.json").resolve()
    return asyncio.run(engine.verify(file_path, {"check_type": check_type}))


_FOO_TERM = {
    "term": "Foo",
    "definition": "the foo concept",
    "not": "not bar",
    "authoritative_paper": ".specs/papers/CORE-Vocabulary.md",
}


# ---------------------------------------------------------------------------
# vocabulary_projection_consistency
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_consistency_clean(tmp_path: Path) -> Path:
    md = _md(
        [("Foo", "the foo concept", "not bar", ".specs/papers/CORE-Vocabulary.md")]
    )
    vocab = _vocab_json([_FOO_TERM], _hash_canonical(md))
    return _build_repo(tmp_path, md, vocab)


@pytest.fixture
def repo_consistency_orphan(tmp_path: Path) -> Path:
    """Projection has an extra term not in the canonical section."""
    md = _md(
        [("Foo", "the foo concept", "not bar", ".specs/papers/CORE-Vocabulary.md")]
    )
    vocab = _vocab_json(
        [
            _FOO_TERM,
            {
                "term": "OrphanTerm",
                "definition": "ghost",
                "not": "real",
                "authoritative_paper": ".specs/papers/CORE-Vocabulary.md",
            },
        ],
        _hash_canonical(md),
    )
    return _build_repo(tmp_path, md, vocab)


def test_projection_consistency_clean(repo_consistency_clean: Path) -> None:
    result = _verify(repo_consistency_clean, "vocabulary_projection_consistency")
    assert result.ok, result.violations


def test_projection_consistency_orphan(repo_consistency_orphan: Path) -> None:
    result = _verify(repo_consistency_orphan, "vocabulary_projection_consistency")
    assert not result.ok
    assert len(result.violations) >= 1
    assert any("OrphanTerm" in v for v in result.violations)


# ---------------------------------------------------------------------------
# vocabulary_canonical_format
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_format_clean(tmp_path: Path) -> Path:
    md = _md(
        [("Foo", "the foo concept", "not bar", ".specs/papers/CORE-Vocabulary.md")]
    )
    vocab = _vocab_json([_FOO_TERM], _hash_canonical(md))
    return _build_repo(tmp_path, md, vocab)


@pytest.fixture
def repo_format_empty_term(tmp_path: Path) -> Path:
    """A data row with an empty 'term' cell."""
    md = _md([("", "the foo concept", "not bar", ".specs/papers/CORE-Vocabulary.md")])
    # Projection still has a non-empty term so projection_consistency would
    # also fail, but this test exercises the canonical_format check only.
    vocab = _vocab_json([_FOO_TERM], _hash_canonical(md))
    return _build_repo(tmp_path, md, vocab)


def test_canonical_format_clean(repo_format_clean: Path) -> None:
    result = _verify(repo_format_clean, "vocabulary_canonical_format")
    assert result.ok, result.violations


def test_canonical_format_empty_term(repo_format_empty_term: Path) -> None:
    result = _verify(repo_format_empty_term, "vocabulary_canonical_format")
    assert not result.ok
    assert len(result.violations) >= 1
    assert any("'term' is empty" in v for v in result.violations)


# ---------------------------------------------------------------------------
# vocabulary_authoritative_paths
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_paths_clean(tmp_path: Path) -> Path:
    md = _md(
        [("Foo", "the foo concept", "not bar", ".specs/papers/CORE-Vocabulary.md")]
    )
    vocab = _vocab_json([_FOO_TERM], _hash_canonical(md))
    return _build_repo(tmp_path, md, vocab)


@pytest.fixture
def repo_paths_nonexistent(tmp_path: Path) -> Path:
    """authoritative_paper points to a file that does not exist."""
    md = _md([("Foo", "the foo concept", "not bar", ".specs/papers/NONEXISTENT.md")])
    vocab = _vocab_json(
        [
            {
                "term": "Foo",
                "definition": "the foo concept",
                "not": "not bar",
                "authoritative_paper": ".specs/papers/NONEXISTENT.md",
            }
        ],
        _hash_canonical(md),
    )
    return _build_repo(tmp_path, md, vocab)


def test_authoritative_paths_clean(repo_paths_clean: Path) -> None:
    result = _verify(repo_paths_clean, "vocabulary_authoritative_paths")
    assert result.ok, result.violations


def test_authoritative_paths_nonexistent(repo_paths_nonexistent: Path) -> None:
    result = _verify(repo_paths_nonexistent, "vocabulary_authoritative_paths")
    assert not result.ok
    assert len(result.violations) >= 1
    assert any("NONEXISTENT.md" in v for v in result.violations)
