# src/shared/utils/import_scanner.py
"""
Scans Python files to extract top-level import statements.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List

from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: code.import.scan_file
def scan_imports_for_file(file_path: Path) -> List[str]:
    """
    Parse a Python file and extract all imported module paths.

    Args:
        file_path (Path): Path to the file.

    Returns:
        List[str]: List of imported module paths.
    """
    imports = []
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

    except Exception as e:
        log.warning(f"Failed to scan imports for {file_path}: {e}", exc_info=True)

    return imports
