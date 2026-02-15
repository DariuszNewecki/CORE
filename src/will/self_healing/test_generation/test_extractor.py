# src/features/self_healing/test_generation/test_extractor.py

"""Specialist for surgical AST-based code extraction and replacement."""

from __future__ import annotations

import ast
from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler


# ID: cccc1d15-a41a-4c4c-8860-cc61a97e8b7e
class TestExtractor:
    """Extracts and replaces individual test functions in test files."""

    def __init__(self, file_handler: FileHandler, repo_root: Path):
        self.file_handler = file_handler
        self.repo_root = repo_root

    # ID: 7f3249d6-5e80-45ea-9e25-19e4e42030d0
    def extract_test_function(self, file_path: Path, test_name: str) -> str | None:
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == test_name:
                    return ast.get_source_segment(content, node)
            return None
        except Exception:
            return None

    # ID: b3943163-5281-4ec4-a75e-180ce9dee743
    def replace_test_function(
        self, file_path: Path, test_name: str, new_code: str
    ) -> bool:
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == test_name:
                    original = ast.get_source_segment(content, node)
                    if original:
                        new_content = content.replace(original, new_code, 1)
                        rel_path = str(file_path.relative_to(self.repo_root))
                        self.file_handler.write_runtime_text(rel_path, new_content)
                        return True
            return False
        except Exception:
            return False
