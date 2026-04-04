# src/body/atomic/import_resolver.py

"""
Deterministic import resolver for modularization splits.

Given a file's full source and a list of symbol names destined for one
target module, determines the minimal set of import statements those
symbols actually need.

Constitutional note:
  Body layer — no settings access, no file I/O, no LLM calls.
  Operates on source strings only.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    pass


# ID: 7c2e8f1a-4b3d-4a59-9e6c-0d1f2a3b4c5e
class ImportResolver:
    """Resolve the minimal imports needed by a subset of symbols."""

    # ID: 9a0b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
    def resolve(self, source: str, symbol_names: list[str]) -> list[str]:
        """Return minimal import statement strings for *symbol_names*.

        Parameters
        ----------
        source:
            Full source code of the file being split.
        symbol_names:
            Top-level symbol names assigned to one target module.

        Returns
        -------
        list[str]
            Import statement source lines needed by those symbols.
            ``__future__`` imports and ``TYPE_CHECKING`` blocks are
            always included.
        """
        tree = ast.parse(source)
        source_lines = source.splitlines(keepends=True)

        # --- collect top-level import nodes and their source text ----------
        import_nodes: list[ast.stmt] = []
        type_checking_block: list[ast.stmt] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_nodes.append(node)
            elif isinstance(node, ast.If) and self._is_type_checking_guard(node):
                type_checking_block.append(node)

        # --- classify imports ----------------------------------------------
        future_imports: list[str] = []
        regular_imports: list[tuple[ast.stmt, str]] = []

        for node in import_nodes:
            stmt_text = self._node_source(node, source_lines)
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                future_imports.append(stmt_text)
            else:
                regular_imports.append((node, stmt_text))

        # --- collect names referenced by the target symbols ----------------
        needed_names = self._collect_references(tree, symbol_names)

        # --- match regular imports against needed names --------------------
        matched: list[str] = []
        for node, stmt_text in regular_imports:
            if self._import_provides(node, needed_names):
                matched.append(stmt_text)

        # --- assemble result: future → TYPE_CHECKING → matched -------------
        result: list[str] = list(future_imports)

        if type_checking_block:
            for block_node in type_checking_block:
                result.append(self._node_source(block_node, source_lines))

        result.extend(matched)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_type_checking_guard(self, node: ast.If) -> bool:
        """Return True if ``node`` is ``if TYPE_CHECKING:``."""
        test = node.test
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
            return True
        return False

    def _node_source(self, node: ast.stmt, source_lines: list[str]) -> str:
        """Extract the original source text of *node*."""
        # ast nodes have lineno (1-based) and end_lineno
        start = node.lineno - 1
        end = node.end_lineno if node.end_lineno is not None else node.lineno
        return "".join(source_lines[start:end]).rstrip()

    def _collect_references(
        self, tree: ast.Module, symbol_names: list[str]
    ) -> set[str]:
        """Collect all bare-name and attribute-root references used by *symbol_names*."""
        target_nodes: list[ast.AST] = []
        name_set = set(symbol_names)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in name_set:
                    target_nodes.append(node)
                    # Also grab decorator references
                    for deco in node.decorator_list:
                        target_nodes.append(deco)

        names: set[str] = set()
        for target in target_nodes:
            for child in ast.walk(target):
                if isinstance(child, ast.Name):
                    names.add(child.id)
                elif isinstance(child, ast.Attribute):
                    root = self._attribute_root(child)
                    if root:
                        names.add(root)

        return names

    def _attribute_root(self, node: ast.Attribute) -> str | None:
        """Walk ``a.b.c`` to return ``'a'``."""
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            current = current.value
        if isinstance(current, ast.Name):
            return current.id
        return None

    def _import_provides(self, node: ast.stmt, needed: set[str]) -> bool:
        """Return True if *node* provides any name in *needed*."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound in needed:
                    return True
        elif isinstance(node, ast.ImportFrom):
            module_root = (node.module or "").split(".")[0]
            if module_root in needed:
                return True
            for alias in node.names:
                bound = alias.asname or alias.name
                if bound in needed:
                    return True
        return False
