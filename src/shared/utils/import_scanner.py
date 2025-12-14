# src/shared/utils/import_scanner.py

"""
Scans Python files to extract top-level import statements.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: eba232a5-650f-4b18-ab04-e5a86e590d09
def scan_imports_for_file(file_path: Path) -> list[str]:
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
        logger.warning("Failed to scan imports for %s: %s", file_path, e, exc_info=True)
    return imports
