# src/mind/logic/engines/ast_gate/checks/metadata_checks.py
# ID: d91d9ba4-c276-4cb2-ad25-eaa4e1284d5c

"""
Metadata Mutation Verification Engine.

Proves that a file mutation is metadata-only by comparing normalized ASTs.
This is the enforcement arm of the metadata.semantic_preservation constitutional rule.

INVARIANT: normalize_ast(before) == normalize_ast(after)

Normalization strips:
- All comments (invisible to AST)
- All docstrings (Expr(Constant(str)) at head of body)
- All line/col numbers (positional attributes)

If the normalized ASTs match, the mutation touched ONLY metadata.
If they differ, executable semantics changed — violation.
"""

from __future__ import annotations

import ast
from typing import Any


# ID: 79c7e3a6-700a-44e8-b1cc-376f7d1d4736
# ID: 30421199-33fe-48fc-961a-912cd8459ad9
def normalize_ast(code: str) -> str:
    """
    Parse code and produce a canonical AST string with docstrings and
    line numbers stripped.

    Args:
        code: Python source code

    Returns:
        Deterministic string representation of the executable AST.

    Raises:
        SyntaxError: If code cannot be parsed.
    """
    tree = ast.parse(code)
    _strip_docstrings(tree)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


# ID: 3f49383d-5e9e-400a-b9b5-cc4883a7cb9a
# ID: 7b7c431d-8341-4263-98bf-13cf15ad7ae1
def verify_metadata_only_diff(
    original_code: str,
    modified_code: str,
    params: dict[str, Any] | None = None,
) -> list[str]:
    """
    Core enforcement: prove that a mutation is metadata-only.

    Returns a list of violation strings (empty = passed).

    Checks performed:
    1. Normalized AST identity (the invariant)
    2. Comment length constraints (if max_comment_length specified)
    3. Operation type validation (if allowed_operations specified)
    """
    params = params or {}
    violations: list[str] = []

    # ------------------------------------------------------------------
    # GATE 1: Semantic Preservation (the constitutional invariant)
    # ------------------------------------------------------------------
    try:
        norm_before = normalize_ast(original_code)
    except SyntaxError as e:
        violations.append(f"Original code has syntax error: {e}")
        return violations

    try:
        norm_after = normalize_ast(modified_code)
    except SyntaxError as e:
        violations.append(f"Modified code has syntax error: {e}")
        return violations

    if norm_before != norm_after:
        violations.append(
            "SEMANTIC PRESERVATION VIOLATED: "
            "The normalized AST differs before and after the mutation. "
            "This is not a metadata-only change."
        )
        return violations  # Fail-fast — no point checking details

    # ------------------------------------------------------------------
    # GATE 2: Comment length constraints
    # ------------------------------------------------------------------
    max_len = params.get("max_comment_length")
    if max_len is not None:
        max_len = int(max_len)
        before_lines = set(original_code.splitlines())
        after_lines = modified_code.splitlines()

        for i, line in enumerate(after_lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#") and line not in before_lines:
                if len(stripped) > max_len:
                    violations.append(
                        f"Line {i}: New comment exceeds {max_len} chars "
                        f"({len(stripped)} chars): {stripped[:60]}..."
                    )

    # ------------------------------------------------------------------
    # GATE 3: Operation type validation
    # ------------------------------------------------------------------
    allowed_ops = params.get("allowed_operations")
    if allowed_ops is not None:
        detected_ops = _detect_operations(original_code, modified_code)
        disallowed = detected_ops - set(allowed_ops)
        if disallowed:
            violations.append(
                f"Disallowed metadata operations detected: {sorted(disallowed)}. "
                f"Permitted: {sorted(allowed_ops)}"
            )

    return violations


# ID: e202d440-62a4-4918-acad-4674bbc2a85a
def _strip_docstrings(tree: ast.AST) -> None:
    """
    Remove docstring nodes from an AST in-place.

    Docstrings are the first Expr(Constant(str)) in the body of:
    - Module
    - ClassDef
    - FunctionDef / AsyncFunctionDef
    """
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body.pop(0)
                # If body is now empty, add Pass to keep valid AST
                if not node.body:
                    node.body.append(ast.Pass())


# ID: 5e7a126e-3f40-4d05-8219-2a796178a83b
def _detect_operations(original: str, modified: str) -> set[str]:
    """
    Detect which metadata operation types occurred between original and modified.

    Returns a set of operation strings like:
    {"comment.insert", "comment.delete", "docstring.insert", etc.}
    """
    ops: set[str] = set()

    # --- Comment detection (line-level diff) ---
    before_lines = original.splitlines()
    after_lines = modified.splitlines()

    before_comments = {
        line.lstrip() for line in before_lines if line.lstrip().startswith("#")
    }
    after_comments = {
        line.lstrip() for line in after_lines if line.lstrip().startswith("#")
    }

    new_comments = after_comments - before_comments
    removed_comments = before_comments - after_comments

    if new_comments and removed_comments:
        # Some added, some removed — could be insert + delete, or replace
        # If counts match and content changed, likely replace
        ops.add("comment.replace")
    if new_comments and not removed_comments:
        ops.add("comment.insert")
    if removed_comments and not new_comments:
        ops.add("comment.delete")
    if new_comments and removed_comments:
        # Also count as insert/delete for completeness
        ops.add("comment.insert")
        ops.add("comment.delete")

    # --- Docstring detection (AST-level diff) ---
    try:
        before_docstrings = _extract_docstrings(original)
        after_docstrings = _extract_docstrings(modified)

        before_keys = set(before_docstrings.keys())
        after_keys = set(after_docstrings.keys())

        new_ds = after_keys - before_keys
        removed_ds = before_keys - after_keys
        common_ds = before_keys & after_keys

        if new_ds:
            ops.add("docstring.insert")
        if removed_ds:
            ops.add("docstring.delete")
        for key in common_ds:
            if before_docstrings[key] != after_docstrings[key]:
                ops.add("docstring.replace")
    except SyntaxError:
        pass  # AST comparison already caught this in Gate 1

    return ops


# ID: e5997fbc-bcf6-4b1c-9442-2d67e376d4fc
def _extract_docstrings(code: str) -> dict[str, str]:
    """
    Extract all docstrings keyed by their owner's qualified name.

    Returns: {"Module": "...", "Foo": "...", "Foo.bar": "...", ...}
    """
    tree = ast.parse(code)
    result: dict[str, str] = {}

    def _visit(node: ast.AST, prefix: str = "") -> None:
        targets = []
        if isinstance(node, ast.Module):
            targets = [("Module", node)]
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{prefix}.{node.name}" if prefix else node.name
            targets = [(name, node)]

        for name, target in targets:
            if (
                target.body
                and isinstance(target.body[0], ast.Expr)
                and isinstance(target.body[0].value, ast.Constant)
                and isinstance(target.body[0].value.value, str)
            ):
                result[name] = target.body[0].value.value

            for child in ast.iter_child_nodes(target):
                child_prefix = name if name != "Module" else ""
                _visit(child, child_prefix)

    _visit(tree)
    return result
