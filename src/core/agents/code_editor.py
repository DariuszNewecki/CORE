# src/agents/code_editor.py
"""
Editing primitives for code manipulation used by agents.

Owns the code-editing capabilities previously defined in agents.utils.
"""

from __future__ import annotations

import ast
import textwrap
from typing import Optional, Tuple


# ID: 034c41cd-f072-4a4f-adf9-9aaecbd7b7e9
class CodeEditor:
    """Provides capabilities to surgically edit code files."""

    def _get_symbol_start_end_lines(
        self, tree: ast.AST, symbol_name: str
    ) -> Optional[Tuple[int, int]]:
        """Finds the 1-based start and end line numbers of a symbol."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    if hasattr(node, "end_lineno") and node.end_lineno is not None:
                        return node.lineno, node.end_lineno
        return None

    # ID: 39521cc6-f4d0-4236-a0b9-3f5b1eb04312
    def replace_symbol_in_code(
        self, original_code: str, symbol_name: str, new_code_str: str
    ) -> str:
        """
        Replaces a function/method in code with a new version using a line-based strategy.
        """
        try:
            original_tree = ast.parse(original_code)
        except SyntaxError as e:
            raise ValueError(f"Could not parse original code due to syntax error: {e}")

        symbol_location = self._get_symbol_start_end_lines(original_tree, symbol_name)
        if not symbol_location:
            raise ValueError(f"Symbol '{symbol_name}' not found in the original code.")

        start_line, end_line = symbol_location
        start_index = start_line - 1
        end_index = end_line

        lines = original_code.splitlines()

        original_line = lines[start_index]
        indentation = len(original_line) - len(original_line.lstrip(" "))

        clean_new_code = textwrap.dedent(new_code_str).strip()
        new_code_lines = clean_new_code.splitlines()
        indented_new_code_lines = [
            f"{' ' * indentation}{line}" for line in new_code_lines
        ]

        code_before = lines[:start_index]
        code_after = lines[end_index:]

        final_lines = code_before + indented_new_code_lines + code_after
        return "\n".join(final_lines)
