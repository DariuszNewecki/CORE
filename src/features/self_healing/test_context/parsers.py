# src/features/self_healing/test_context/parsers.py

"""Refactored logic for src/features/self_healing/test_context/parsers.py."""

from __future__ import annotations

import ast
from typing import Any


# ID: 02c15180-d580-44dc-9e1a-1389d1bf16b1
def extract_classes(tree: ast.AST) -> list[dict[str, Any]]:
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [
                {
                    "name": i.name,
                    "docstring": ast.get_docstring(i),
                    "is_private": i.name.startswith("_"),
                    "args": [a.arg for a in i.args.args],
                }
                for i in node.body
                if isinstance(i, ast.FunctionDef)
            ]
            classes.append(
                {
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "methods": methods,
                    "bases": [get_node_name(b) for b in node.bases],
                }
            )
    return classes


# ID: 74d8bef6-1e3a-4cf6-821a-afbb5f73c20b
def extract_functions(tree: ast.AST) -> list[dict[str, Any]]:
    return [
        {
            "name": n.name,
            "docstring": ast.get_docstring(n),
            "is_private": n.name.startswith("_"),
            "is_async": isinstance(n, ast.AsyncFunctionDef),
            "args": [a.arg for a in n.args.args],
        }
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
    ]


# ID: ca485404-dd90-40b7-ad92-6ecf6662d455
def extract_imports(tree: ast.AST) -> list[str]:
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return list(imports)


# ID: 265374a7-bcf7-44fc-b776-e89909c89f10
def get_node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{get_node_name(node.value)}.{node.attr}"
    return str(node)
