# src/features/introspection/sync/scanner.py

"""Refactored logic for src/features/introspection/sync/scanner.py."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

# REFACTORED: Removed direct settings import
from shared.utils.domain_mapper import map_module_to_domain

from .visitor import SymbolVisitor


logger = logging.getLogger(__name__)


# ID: 73de4c04-495b-4ecb-bf94-04e06acdbf2d
class SymbolScanner:
    """Scans the codebase to extract symbol information."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    # ID: 3659a617-162e-41e5-979d-af439c230b17
    def scan(self) -> list[dict[str, Any]]:
        src_dir = self.repo_root / "src"
        all_symbols: list[dict[str, Any]] = []

        if not src_dir.exists():
            logger.warning("Source directory not found: %s", src_dir)
            return []

        for file_path in src_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                rel_path_str = str(file_path.relative_to(self.repo_root))

                module_path = rel_path_str.replace(".py", "").replace("/", ".")
                domain = map_module_to_domain(module_path)

                visitor = SymbolVisitor(rel_path_str)
                visitor.visit(tree)

                for sym in visitor.symbols:
                    sym["domain"] = domain
                    all_symbols.append(sym)
            except Exception as exc:
                logger.error("Error scanning %s: %s", file_path, exc)

        unique_symbols = {s["symbol_path"]: s for s in all_symbols}
        return list(unique_symbols.values())
