# src/shared/utils/test_gen_utils.py
"""
Pure AST utilities for test generation.

Extracted from body/atomic/build_test_for_symbol_action.py (ADR-140 D7).
Shared so both the Will-tier cognitive delegate and any future callers can
use them without importing Body infrastructure.

All functions are pure: no I/O, no side effects, no external dependencies
beyond the standard library.
"""

from __future__ import annotations

import ast
from pathlib import Path


# ID: e849337b-b8f4-4d34-8681-a5b42e6aae73
def extract_symbol_code(source_path: Path, symbol_name: str) -> str | None:
    """Extract the source text of a named symbol via AST.

    ``symbol_name`` is either a plain top-level function/class name, or a
    dotted ``ClassName.method_name`` reference to a method nested inside a
    class (test-gen's ``symbol_kind == "method"`` case). A bare top-level
    scan with ``ast.iter_child_nodes(tree)`` never matches a dotted name —
    no top-level node's ``.name`` is ever ``"ClassName.method_name"`` — so
    that case silently returned None, and callers fell back to a bare
    signature comment with no real implementation for the LLM to ground a
    test in (confirmed cause of outright-hallucinated mocks for method-kind
    symbols; ~40% of failed will/workers test-gen attempts are method-kind).
    """
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return None

    class_name, _dot, method_name = symbol_name.partition(".")
    if method_name:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in ast.iter_child_nodes(node):
                    if (
                        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and child.name == method_name
                    ):
                        return ast.get_source_segment(source, child)
                return None
        return None

    for node in ast.iter_child_nodes(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == symbol_name
        ):
            return ast.get_source_segment(source, node)
    return None


# ID: a06176f3-724b-41d2-9de5-2cd7429f9c4a
def extract_constructor_signature(source_path: Path, class_name: str) -> str | None:
    """Extract a class's ``__init__`` source, for method-level test-gen callers.

    Method-level extraction (``extract_symbol_code`` with a dotted
    ``ClassName.method_name``) returns only the method's own body — the
    containing class's constructor is never included, so an LLM generating
    a test for that method has no way to know whether the class needs
    constructor arguments. Confirmed live: db_sync_worker.py's DbSyncWorker
    requires ``core_context`` in ``__init__`` (not the common no-arg worker
    pattern), and two independent generation attempts both produced
    ``DbSyncWorker()`` with no arguments — a guess from the prompt's general
    guidance, not grounded in code the LLM never saw.

    Returns None if the class or an explicit ``__init__`` isn't found — a
    subclass with no constructor of its own relies on its base class's
    default, which has nothing local to extract; that's useful information
    (absence), not an extraction failure.
    """
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return None

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in ast.iter_child_nodes(node):
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == "__init__"
                ):
                    return ast.get_source_segment(source, child)
            return None
    return None


# ID: 2945734a-9bbb-4ea2-9d28-f3999f938112
def derive_module_path(source_file: str) -> str:
    """Convert repo-relative source path to importable module path.

    "src/will/workers/foo.py" -> "will.workers.foo"
    """
    return source_file.removeprefix("src/").removesuffix(".py").replace("/", ".")


# ID: 30d6be8a-405c-4029-81d0-f330a700d5af
def extract_from_fences(raw: str) -> str | None:
    """Extract code content from ```python ... ``` or ``` ... ``` fences."""
    for fence_start in ("```python", "```"):
        start = raw.find(fence_start)
        if start != -1:
            newline = raw.find("\n", start)
            if newline == -1:
                continue
            end = raw.find("```", newline + 1)
            if end == -1:
                continue
            return raw[newline + 1 : end].strip()
    return None


# ID: c3f027f0-a435-4054-8a6c-7c95472828fe
def format_violations(violations: list[dict]) -> str:
    """Format IntentGuard violations into a concise summary for a repair prompt."""
    lines = []
    for v in violations:
        rule = v.get("rule_name", "unknown")
        msg = v.get("message", "")
        lines.append(f"- [{rule}] {msg}" if msg else f"- [{rule}]")
    return "\n".join(lines) if lines else "Unknown violations"
