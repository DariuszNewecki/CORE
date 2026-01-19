# src/features/introspection/sync/visitor.py

"""Refactored logic for src/features/introspection/sync/visitor.py."""

from __future__ import annotations

import ast
import json
import uuid
from typing import Any

from shared.ast_utility import FunctionCallVisitor, calculate_structural_hash


# ID: d766fc43-dea6-4156-8fe9-f9577416ad31
class SymbolVisitor(ast.NodeVisitor):
    """
    An AST visitor that discovers top-level public symbols, their immediate methods,
    and the symbols they call.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.symbols: list[dict[str, Any]] = []
        self.class_stack: list[str] = []

    # ID: e7f6fab3-cf81-46ff-b2d1-21d7b6f311c6
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self.class_stack:
            self._process_symbol(node)
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

    # ID: 056a919f-fe43-4bab-9398-48c93c971545
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if len(self.class_stack) <= 1:
            self._process_symbol(node)

    # ID: aae1a414-338b-4a62-bb93-5a5a6b22a1fa
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if len(self.class_stack) <= 1:
            self._process_symbol(node)

    def _process_symbol(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        is_public = not node.name.startswith("_")
        is_dunder = node.name.startswith("__") and node.name.endswith("__")
        if not (is_public and not is_dunder):
            return

        path_components = [*self.class_stack, node.name]
        symbol_path = f"{self.file_path}::{'.'.join(path_components)}"
        qualname = ".".join(path_components)

        module_name = (
            self.file_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        kind_map = {
            "ClassDef": "class",
            "FunctionDef": "function",
            "AsyncFunctionDef": "function",
        }

        call_visitor = FunctionCallVisitor()
        call_visitor.visit(node)
        calls = sorted(list(call_visitor.calls))

        self.symbols.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, symbol_path),
                "symbol_path": symbol_path,
                "module": module_name,
                "qualname": qualname,
                "kind": kind_map.get(type(node).__name__, "function"),
                "ast_signature": "pending",
                "fingerprint": calculate_structural_hash(node),
                "state": "discovered",
                "is_public": True,
                "calls": json.dumps(calls),
            }
        )
