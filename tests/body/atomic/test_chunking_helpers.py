"""Tests for src/body/atomic/sync_actions/chunking_helpers.py.

Covers the empty-content fix: `_chunk_whole` must return no chunks for
empty/whitespace-only content, not a single empty-text chunk. A non-empty
chunk list bypasses `sync_actions.py`'s `if not chunks: mark_artifact_empty()`
guard — the embedder short-circuits empty text to `None`, which
`_embed_and_upsert` silently drops, leaving `chunk_count` stuck at 0
forever (never reaches the -1 permanently-skipped terminal state).
"""

from body.atomic.sync_actions.chunking_helpers import (
    _chunk_by_symbol,
    _chunk_file,
    _chunk_whole,
)


def test_chunk_whole_empty_content_returns_no_chunks():
    assert _chunk_whole("", "some/file.py") == []


def test_chunk_whole_whitespace_only_content_returns_no_chunks():
    assert _chunk_whole("   \n\n\t  \n", "some/file.py") == []


def test_chunk_whole_non_empty_content_returns_one_chunk():
    chunks = _chunk_whole("hello world", "some/file.py")
    assert len(chunks) == 1
    assert chunks[0]["text"] == "hello world"
    assert chunks[0]["metadata"]["source"] == "some/file.py"


def test_chunk_by_symbol_empty_python_source_returns_no_chunks():
    """The exact failure scenario: an empty .py file with no functions or
    classes must fall through to zero chunks, not one empty-text chunk."""
    assert _chunk_by_symbol("", "src/pkg/__init__.py") == []


def test_chunk_by_symbol_whitespace_only_python_source_returns_no_chunks():
    assert _chunk_by_symbol("\n\n   \n", "src/pkg/__init__.py") == []


def test_chunk_by_symbol_with_function_still_chunks():
    content = "def foo():\n    return 1\n"
    chunks = _chunk_by_symbol(content, "src/pkg/mod.py")
    assert len(chunks) == 1
    assert "def foo" in chunks[0]["text"]
    assert chunks[0]["metadata"]["chunk_type"] == "function"


def test_chunk_file_empty_python_file_returns_no_chunks(tmp_path):
    empty_file = tmp_path / "__init__.py"
    empty_file.write_text("", encoding="utf-8")
    assert _chunk_file(empty_file, "python") == []
