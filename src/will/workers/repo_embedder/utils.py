# utils.py
"""Utility functions for file chunking based on different types of artifacts"""

from __future__ import annotations

from typing import Any


def _chunk_by_symbol(content: str, source: str) -> list[dict[str, Any]]:
    """
    Chunk Python source by class and function boundaries using AST.

    Each top-level class and function becomes one chunk (with its full body).
    Nested functions inside classes are included in the class chunk rather
    than split out — this preserves semantic coherence.

    Falls back to _chunk_by_heading on syntax errors.
    """
    import ast as _ast

    chunks = []
    lines = content.splitlines()

    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return _chunk_by_heading(content, source)

    # Only visit top-level nodes (module body)
    for node in tree.body:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = node.end_lineno or (start + 30)
            text = "\n".join(lines[start:end]).strip()
            if text:
                chunks.extend(
                    _split_large(
                        text,
                        source,
                        node.name,
                        chunk_type="function",
                    )
                )

        elif isinstance(node, _ast.ClassDef):
            start = node.lineno - 1
            end = node.end_lineno or (start + 50)
            text = "\n".join(lines[start:end]).strip()
            if text:
                chunks.extend(
                    _split_large(
                        text,
                        source,
                        node.name,
                        chunk_type="class",
                    )
                )

    if not chunks:
        # Module has no top-level classes/functions — embed whole file
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
