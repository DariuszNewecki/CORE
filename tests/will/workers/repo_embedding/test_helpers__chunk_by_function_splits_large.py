"""#890: `_chunk_by_function` (the `test` artifact chunker) must split
oversized test functions like every other chunker does.

A single 10.5k-char test function was sent to Ollama whole, got a
deterministic 400 ("input length exceeds the context length"), was retried
4x every 10-minute cycle for days, and the artifact was never embedded.
"""

from __future__ import annotations

import dataclasses

from will.workers.repo_embedding import helpers


def _with_max_chunk_chars(monkeypatch, n: int) -> None:
    """_CFG_CHK is a frozen dataclass -- swap the module binding, not a field."""
    monkeypatch.setattr(
        helpers, "_CFG_CHK", dataclasses.replace(helpers._CFG_CHK, max_chunk_chars=n)
    )


def _big_test_module(body_lines: int) -> str:
    body = "\n".join(
        f"    x_{i} = {i}  # padding line to inflate the function"
        for i in range(body_lines)
    )
    return f"import pytest\n\n\ndef test_huge():\n{body}\n    assert True\n\n\ndef test_small():\n    assert 1 == 1\n"


def test_oversized_test_function_is_split_into_bounded_chunks(monkeypatch) -> None:
    _with_max_chunk_chars(monkeypatch, 600)
    chunks = helpers._chunk_by_function(_big_test_module(80), "tests/t.py")

    huge = [c for c in chunks if c["metadata"]["section"].startswith("test_huge")]
    small = [c for c in chunks if c["metadata"]["section"] == "test_small"]

    assert len(huge) > 1, "oversized function must be split"
    assert all(len(c["text"]) <= 600 for c in huge)
    assert all(c["metadata"]["chunk_type"] == "test_function" for c in huge)
    assert [c["metadata"]["section"] for c in huge] == [
        f"test_huge_part{i}" for i in range(len(huge))
    ]
    assert len(small) == 1 and small[0]["metadata"]["section"] == "test_small"


def test_small_test_function_is_one_chunk_unchanged(monkeypatch) -> None:
    _with_max_chunk_chars(monkeypatch, 1500)
    chunks = helpers._chunk_by_function(_big_test_module(2), "tests/t.py")
    assert [c["metadata"]["section"] for c in chunks] == ["test_huge", "test_small"]
