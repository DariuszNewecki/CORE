# chunking_strategies.py
"""Utility functions for chunking and splitting code artifacts"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _chunk_file(file_path: Path, artifact_type: str) -> list[dict[str, Any]]:
    """
    Chunk a file into semantic units for embedding.
    Returns list of chunk dicts: {text, metadata}.
    """
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
