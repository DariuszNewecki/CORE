# src/will/tools/anchors/discovery.py

"""Refactored logic for src/will/tools/anchors/discovery.py."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


# ID: a5d1ed56-ee9c-4bbb-a913-7e264b9f0e11
def discover_modules_for_layers(
    src_dir: Path, layers: list[str]
) -> dict[Path, dict[str, Any]]:
    """Recursive glob scanning of src/ to find modules within defined layers."""
    modules = {}
    for layer_name in layers:
        layer_dir = src_dir / layer_name
        if not layer_dir.exists():
            continue
        for item in layer_dir.rglob("*"):
            if item.is_dir() and (not item.name.startswith("_")):
                py_files = list(item.glob("*.py"))
                if py_files:
                    relative_path = item.relative_to(src_dir)
                    modules[relative_path] = {
                        "layer": layer_name,
                        "docstring": _extract_module_docstring(item),
                        "file_count": len(py_files),
                        "python_files": [f.name for f in py_files[:5]],
                    }
    return modules


def _extract_module_docstring(module_dir: Path) -> str | None:
    """Extract module-level docstring from __init__.py via AST."""
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return None
    try:
        content = init_file.read_text(encoding="utf-8")
        tree = ast.parse(content)
        if tree.body and isinstance(tree.body[0], ast.Expr):
            if isinstance(tree.body[0].value, ast.Constant):
                value = tree.body[0].value.value

                # TYPE GUARD: Ensure it's actually a string
                if isinstance(value, str):
                    return value
                # Otherwise, not a docstring (maybe a number constant?)

    except Exception:
        pass
    return None
