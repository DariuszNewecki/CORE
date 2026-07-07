# tests/mind/logic/engines/test_knowledge_gate__semantic_duplication.py

"""Unit tests for _check_semantic_duplication in _knowledge_gate_duplication.py.

All Qdrant calls are mocked so these run without a live Qdrant instance.
The tests exercise:
  - Early-exit guards (no qdrant_service, collection absent, no matching chunks)
  - Pair detection above threshold in different files
  - Same-file pair suppression
  - Sub-threshold pair suppression
  - Test-file exclusion
  - _sym_from_chunk helper
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mind.logic.engines._knowledge_gate_duplication import (
    _check_semantic_duplication,
    _sym_from_chunk,
)


def _make_context(*, symbols_map: dict | None = None, qdrant: Any = None) -> MagicMock:
    ctx = MagicMock()
    ctx.symbols_map = symbols_map if symbols_map is not None else {"sym": {}}
    ctx.qdrant_service = qdrant
    return ctx


def _unit_vec(n: int, idx: int) -> list[float]:
    """Return a unit vector of length n with 1.0 at position idx, 0 elsewhere."""
    v = [0.0] * n
    v[idx] = 1.0
    return v


def _similar_vec(base: list[float], noise: float = 0.01) -> list[float]:
    """Return a vector very close to base (cosine similarity > 0.99).

    Adds noise to the last dimension (not the first) so that normalization does
    not cancel the perturbation when base is a unit vector at index 0.
    """
    perturbed = [x + noise if i == len(base) - 1 else x for i, x in enumerate(base)]
    mag = math.sqrt(sum(x * x for x in perturbed))
    return [x / mag for x in perturbed]


def _make_qdrant_point(
    file_path: str,
    section: str,
    vector: list[float],
    chunk_type: str = "function",
    artifact_type: str = "python",
) -> MagicMock:
    point = MagicMock()
    point.payload = {
        "file_path": file_path,
        "section": section,
        "chunk_type": chunk_type,
        "artifact_type": artifact_type,
    }
    point.vector = vector
    return point


def _make_qdrant(*, collections: list[str], points: list[MagicMock]) -> MagicMock:
    qdrant = MagicMock()
    qdrant.collection_name = "core-code"
    qdrant.list_collections = AsyncMock(return_value=collections)
    qdrant.scroll_all_points = AsyncMock(return_value=points)
    return qdrant


# ── _sym_from_chunk ──────────────────────────────────────────────────────────


# ID: 06b02e43-400b-46fa-a321-72ba07f3f493
def test_sym_from_chunk_builds_correct_fields() -> None:
    chunk = {"file_path": "src/body/foo.py", "section": "do_thing", "vector": []}
    sym = _sym_from_chunk(chunk)
    assert sym["qualname"] == "do_thing"
    assert sym["name"] == "do_thing"
    assert sym["file_path"] == "src/body/foo.py"
    assert sym["module"] == "src.body.foo"


# ID: 9e693ec7-e520-4775-9370-ede073697b29
def test_sym_from_chunk_missing_section_falls_back_to_question_mark() -> None:
    chunk = {"file_path": "src/x.py", "section": "", "vector": []}
    sym = _sym_from_chunk(chunk)
    assert sym["qualname"] == "?"
    assert sym["name"] == "?"


# ── guard conditions ─────────────────────────────────────────────────────────


# ID: a6da3899-8cf9-444e-9c37-91b9db237afb
@pytest.mark.asyncio
async def test_returns_empty_when_no_qdrant_service() -> None:
    ctx = _make_context(qdrant=None)
    result = await _check_semantic_duplication(ctx, {})
    assert result == []


# ID: bc49bb2a-2970-47d7-8d38-e1e9bbbbaa9b
@pytest.mark.asyncio
async def test_returns_empty_when_collection_absent() -> None:
    qdrant = _make_qdrant(collections=["other-collection"], points=[])
    ctx = _make_context(qdrant=qdrant)
    result = await _check_semantic_duplication(ctx, {"threshold": 0.85})
    assert result == []
    qdrant.scroll_all_points.assert_not_called()


# ID: 61dc299b-cda7-4d1d-a66b-c12e3433d842
@pytest.mark.asyncio
async def test_returns_empty_when_no_matching_chunks() -> None:
    # Only non-python chunks in the collection
    points = [
        _make_qdrant_point("docs/guide.md", "intro", [1.0, 0.0], artifact_type="doc"),
    ]
    qdrant = _make_qdrant(collections=["core-code"], points=points)
    ctx = _make_context(qdrant=qdrant)
    result = await _check_semantic_duplication(ctx, {"threshold": 0.85})
    assert result == []


# ── detection logic ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detects_similar_functions_in_different_files() -> None:
    """Two near-identical function vectors in different files should produce a finding."""
    dim = 4
    base = _unit_vec(dim, 0)
    similar = _similar_vec(base, noise=0.001)
    points = [
        _make_qdrant_point("src/body/a.py", "process", base),
        _make_qdrant_point("src/body/b.py", "process", similar),
    ]
    qdrant = _make_qdrant(collections=["core-code"], points=points)
    ctx = _make_context(qdrant=qdrant)
    findings = await _check_semantic_duplication(ctx, {"threshold": 0.85})
    assert len(findings) == 1
    assert findings[0].check_id == "purity.no_semantic_duplication"
    assert "semantic" in findings[0].message.lower()


@pytest.mark.asyncio
async def test_no_finding_for_same_file_pair() -> None:
    """Two similar chunks in the same file must not produce a finding."""
    dim = 4
    base = _unit_vec(dim, 0)
    similar = _similar_vec(base, noise=0.001)
    points = [
        _make_qdrant_point("src/body/a.py", "process_a", base),
        _make_qdrant_point("src/body/a.py", "process_b", similar),
    ]
    qdrant = _make_qdrant(collections=["core-code"], points=points)
    ctx = _make_context(qdrant=qdrant)
    findings = await _check_semantic_duplication(ctx, {"threshold": 0.85})
    assert findings == []


@pytest.mark.asyncio
async def test_no_finding_below_threshold() -> None:
    """Orthogonal vectors (cosine sim = 0) must not produce a finding."""
    dim = 4
    points = [
        _make_qdrant_point("src/body/a.py", "foo", _unit_vec(dim, 0)),
        _make_qdrant_point("src/body/b.py", "bar", _unit_vec(dim, 1)),
    ]
    qdrant = _make_qdrant(collections=["core-code"], points=points)
    ctx = _make_context(qdrant=qdrant)
    findings = await _check_semantic_duplication(ctx, {"threshold": 0.85})
    assert findings == []


@pytest.mark.asyncio
async def test_excludes_test_files() -> None:
    """Files with 'test' in their path must be excluded even if highly similar."""
    dim = 4
    base = _unit_vec(dim, 0)
    similar = _similar_vec(base, noise=0.001)
    points = [
        _make_qdrant_point("src/body/a.py", "process", base),
        _make_qdrant_point("tests/body/test_a.py", "process", similar),
    ]
    qdrant = _make_qdrant(collections=["core-code"], points=points)
    ctx = _make_context(qdrant=qdrant)
    findings = await _check_semantic_duplication(ctx, {"threshold": 0.85})
    assert findings == []


@pytest.mark.asyncio
async def test_threshold_governs_detection() -> None:
    """A pair just above threshold is found; the same pair with a raised threshold is not."""
    dim = 4
    base = _unit_vec(dim, 0)
    similar = _similar_vec(base, noise=0.1)  # slightly less similar than noise=0.001
    points = [
        _make_qdrant_point("src/body/a.py", "foo", base),
        _make_qdrant_point("src/body/b.py", "foo", similar),
    ]
    qdrant = _make_qdrant(collections=["core-code"], points=points)
    ctx = _make_context(qdrant=qdrant)

    # Low threshold — should find the pair
    findings_low = await _check_semantic_duplication(ctx, {"threshold": 0.5})
    assert len(findings_low) == 1

    # High threshold (perfect similarity required) — should not find the pair
    findings_high = await _check_semantic_duplication(ctx, {"threshold": 0.9999})
    assert findings_high == []
