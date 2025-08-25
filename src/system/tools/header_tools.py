# src/system/tools/header_tools.py
"""
Provides atomic tools for parsing and reconstructing Python file header decorators including location markers, module descriptions, and future imports.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class ParsedHeader:
    """A structured representation of the decorators in a file's header."""

    location: str | None = None
    module_description: str | None = None
    has_future_import: bool = False
    body_start_line: int = 0
    original_lines: list[str] | None = None


class HeaderTools:
    """A collection of atomic tools for managing file header decorators."""

    @staticmethod
    def parse(file_content: str) -> ParsedHeader:
        """Parses a file's content into its distinct decorator components."""
        lines = file_content.splitlines()
        tree = ast.parse(file_content)

        header = ParsedHeader(original_lines=lines)

        # 1. Find Location Decorator
        if lines and lines[0].strip().startswith("# src/"):
            header.location = lines[0]

        # 2. Find Module Description Decorator
        docstring_node = ast.get_docstring(tree, clean=False)
        if docstring_node:
            # Reconstruct the raw docstring block to preserve quotes
            docstring_start_node = tree.body[0]
            if isinstance(docstring_start_node, ast.Expr):
                start = docstring_start_node.lineno - 1
                end = docstring_start_node.end_lineno
                header.module_description = "\n".join(lines[start:end])

        # 3. Find Future Import
        header.has_future_import = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in tree.body
        )

        # 4. Find where the main code body starts
        for i, node in enumerate(tree.body):
            if i == 0 and header.module_description:
                continue  # Skip the docstring node
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue  # Skip the future import node
            header.body_start_line = node.lineno - 1
            break

        # If no body is found (e.g., file with only a docstring), default to end of file
        if header.body_start_line == 0 and lines:
            header.body_start_line = len(lines)

        return header

    @staticmethod
    def reconstruct(header: ParsedHeader) -> str:
        """Reconstructs a file's content from its decorator components."""
        new_lines = []

        if header.location:
            new_lines.append(header.location)

        if header.module_description:
            if new_lines:
                new_lines.append("")
            new_lines.append(header.module_description)

        if header.has_future_import:
            if new_lines and new_lines[-1] != "":
                new_lines.append("")
            new_lines.append("from __future__ import annotations")

        body = header.original_lines[header.body_start_line :]

        if body:
            if new_lines and new_lines[-1] != "":
                new_lines.append("")
            new_lines.extend(body)

        return "\n".join(new_lines).strip() + "\n"
