# src/body/atomic/path_resolver_rewriter.py
"""
AST helpers for the fix.path_resolver atomic action.

Extracted from fix_actions.py so the two rewrite functions can be tested
in isolation (previously untestable-in-isolation, flagged in the 2026-07-02
external review). Nothing here has I/O or import-time side-effects; every
function is deterministic and pure.

LAYER: body/atomic — pure helper module, no CoreContext, no FileHandler.
"""

from __future__ import annotations

from typing import Any


# Maps governed runtime directory names → PathResolver property names.
# Must stay in sync with PathResolver's public interface.
_PATH_RESOLVER_PROPS: dict[str, str] = {
    "reports": "reports_dir",
    "logs": "logs_dir",
    "prompts": "prompts_dir",
    "exports": "exports_dir",
    "workflows": "workflows_dir",
    "build": "build_dir",
    "context": "context_dir",
}


def _is_target_constant(node: Any) -> bool:
    import ast as _ast

    return (
        isinstance(node, _ast.Constant)
        and isinstance(node.value, str)
        and node.value in _PATH_RESOLVER_PROPS
    )


def _is_embedded_target_constant(node: Any) -> tuple[bool, str, str]:
    """Detect a Constant str whose value starts with a governed dir prefix (e.g. ``reports/``).

    Returns ``(matched, prop_name, remainder)`` where ``prop_name`` is the
    matching PathResolver property and ``remainder`` is the substring after the
    prefix-and-slash. ``remainder`` may be empty for bare cases where only the
    prefix-and-slash is present.
    """
    import ast as _ast

    if not (isinstance(node, _ast.Constant) and isinstance(node.value, str)):
        return False, "", ""
    for prefix, prop_name in _PATH_RESOLVER_PROPS.items():
        head = f"{prefix}/"
        if node.value.startswith(head):
            return True, prop_name, node.value[len(head) :]
    return False, "", ""


def _has_target_descendant(node: Any) -> bool:
    """True if `node` or any descendant BinOp has a matching constant operand.

    Used to skip outer BinOps in chained path-division expressions where the
    runtime directory name appears as an intermediate operand. Detects both
    leaf-target forms and embedded-target forms (where the runtime directory
    name is the prefix of a longer Constant) so nested rewrites do not overlap.
    """
    import ast as _ast

    for sub in _ast.walk(node):
        if isinstance(sub, _ast.BinOp) and isinstance(sub.op, _ast.Div):
            if _is_target_constant(sub.left) or _is_target_constant(sub.right):
                return True
            if _is_embedded_target_constant(sub.right)[0]:
                return True
    return False


def _insert_path_resolver_import(source: str) -> str:
    """Insert ``from shared.path_resolver import PathResolver`` into the module.

    Idempotent — returns `source` unchanged if the import is already present.
    Inserts in alphabetically correct position within the existing first-party
    import block (CORE roots: api, body, cli, mind, shared, will). Falls back
    to appending after the last top-level Import/ImportFrom, or after a module
    docstring if no imports exist.
    """
    import ast as _ast

    import asttokens as _asttokens

    import_line = "from shared.path_resolver import PathResolver"
    if import_line in source:
        return source

    try:
        atok = _asttokens.ASTTokens(source, parse=True)
    except (SyntaxError, ImportError):
        return source
    tree = atok.tree

    new_module = "shared.path_resolver"
    first_party_roots = {"api", "body", "cli", "mind", "shared", "will"}

    # Absolute first-party ImportFrom siblings — same isort group as the new
    # import. Relative imports (level > 0) are excluded; they form a separate
    # group below first-party.
    siblings: list[Any] = []
    for node in tree.body:
        if (
            isinstance(node, _ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.split(".")[0] in first_party_roots
        ):
            siblings.append(node)

    if siblings:
        insert_after = None
        insert_before = None
        for node in siblings:
            if node.module < new_module:
                insert_after = node
            else:
                insert_before = node
                break
        if insert_after is not None:
            _, end = atok.get_text_range(insert_after)
            return source[:end] + "\n" + import_line + source[end:]
        if insert_before is not None:
            start, _ = atok.get_text_range(insert_before)
            return source[:start] + import_line + "\n" + source[start:]

    # No first-party siblings — fall back to appending after the last import.
    last_import = None
    for node in tree.body:
        if isinstance(node, (_ast.Import, _ast.ImportFrom)):
            last_import = node

    if last_import is not None:
        _, end = atok.get_text_range(last_import)
        return source[:end] + "\n" + import_line + source[end:]

    # No imports: insert after module docstring if present, else at top.
    insert_at = 0
    if (
        tree.body
        and isinstance(tree.body[0], _ast.Expr)
        and isinstance(tree.body[0].value, _ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        _, insert_at = atok.get_text_range(tree.body[0])

    return source[:insert_at] + "\n\n" + import_line + "\n" + source[insert_at:]


def _transform_path_resolver(source: str) -> tuple[str, int]:
    """Deterministic AST rewrite of hardcoded runtime dir literals.

    Walks the source for ``BinOp(op=Div)`` nodes where one operand is a
    Constant matching a key in ``_PATH_RESOLVER_PROPS`` (reports, logs, prompts,
    exports, workflows, build, context). Each leaf match is replaced with
    ``PathResolver.from_repo(<other operand>).<dir_property>``. Outer BinOps
    that contain a deeper match are skipped (leaf-only strategy) so source
    edits never overlap. Chained path-division expressions with a runtime
    directory name as an intermediate operand are handled by the leaf
    rewrite alone.

    Returns ``(new_source, replacement_count)``. If the source fails to
    parse, returns ``(source, 0)``.
    """
    import ast as _ast

    try:
        import asttokens as _asttokens

        atok = _asttokens.ASTTokens(source, parse=True)
    except (SyntaxError, ImportError):
        return source, 0
    tree = atok.tree

    replacements: list[tuple[int, int, str]] = []
    for node in _ast.walk(tree):
        if not (isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div)):
            continue

        # Form 0 — leaf target: runtime directory name as a standalone Constant operand.
        if _is_target_constant(node.right):
            target, other = node.right, node.left
            prop_name = _PATH_RESOLVER_PROPS[target.value]
            remainder = ""
        elif _is_target_constant(node.left):
            target, other = node.left, node.right
            prop_name = _PATH_RESOLVER_PROPS[target.value]
            remainder = ""
        else:
            # Form 1 — embedded target: runtime directory name as the prefix of
            # a longer Constant on the right operand.
            matched, prop_name, remainder = _is_embedded_target_constant(node.right)
            if not matched:
                continue
            other = node.left

        if _has_target_descendant(other):
            continue

        other_text = atok.get_text(other)
        base = f"PathResolver.from_repo({other_text}).{prop_name}"
        replacement_text = f'{base} / "{remainder}"' if remainder else base
        start, end = atok.get_text_range(node)
        replacements.append((start, end, replacement_text))

    if not replacements:
        return source, 0

    replacements.sort(key=lambda r: r[0], reverse=True)
    new_source = source
    for start, end, text in replacements:
        new_source = new_source[:start] + text + new_source[end:]

    new_source = _insert_path_resolver_import(new_source)
    return new_source, len(replacements)
