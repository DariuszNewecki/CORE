# src/features/introspection/knowledge_graph_service.py
# ID: b64ba9c9-f55c-4a24-bc2d-d8c2fa04b43e

"""
Knowledge Graph Builder - Pure logic service.

Introspects the codebase and creates an in-memory representation of symbols.
This service is pure: it performs no side effects or disk writes.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from shared.ast_utility import (
    FunctionCallVisitor,
    calculate_structural_hash,
    extract_base_classes,
    extract_docstring,
    extract_parameters,
    parse_metadata_comment,
)
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)


# ID: b64ba9c9-f55c-4a24-bc2d-d8c2fa04b43e
class KnowledgeGraphBuilder:
    """
    Scan source code to build a comprehensive in-memory knowledge graph.

    This service does not interact with databases or write to disk.
    """

    def __init__(self, root_path: Path, workspace: LimbWorkspace | None = None) -> None:
        self.root_path = Path(root_path).resolve()
        self.intent_dir = self.root_path / ".intent"
        self.src_dir = self.root_path / "src"
        self.workspace = workspace
        self.symbols: dict[str, dict[str, Any]] = {}

        self.domain_map = self._load_domain_map()
        self.entry_point_patterns = self._load_entry_point_patterns()

    def _load_domain_map(self) -> dict[str, str]:
        """Load the architectural domain map from the constitution."""
        try:
            structure_path = (
                self.intent_dir / "mind" / "knowledge" / "source_structure.yaml"
            )
            if not structure_path.exists():
                structure_path = (
                    self.intent_dir / "mind" / "knowledge" / "project_structure.yaml"
                )

            if structure_path.exists():
                structure = yaml.safe_load(structure_path.read_text("utf-8")) or {}
                items = structure.get("structure", []) or structure.get(
                    "architectural_domains", []
                )
                return {
                    str(self.src_dir / d.get("path", "").replace("src/", "")): d.get(
                        "domain"
                    )
                    for d in items
                    if "path" in d and "domain" in d
                }
            return {}
        except Exception as exc:
            logger.warning("Failed to load domain map: %s", exc)
            return {}

    def _load_entry_point_patterns(self) -> list[dict[str, Any]]:
        """Load patterns for identifying system entry points."""
        try:
            patterns_path = (
                self.intent_dir / "mind" / "knowledge" / "entry_point_patterns.yaml"
            )
            if patterns_path.exists():
                patterns = yaml.safe_load(patterns_path.read_text("utf-8")) or {}
                return patterns.get("patterns", [])
        except Exception as exc:
            logger.warning("Failed to load entry point patterns: %s", exc)
        return []

    # ID: 75c969e0-5c7c-4f58-9a46-62815947d77a
    def build(self) -> dict[str, Any]:
        """
        Execute the full scan and return the in-memory graph.

        PURE: Does not write reports to disk.
        """
        logger.info("Building knowledge graph (in-memory) for: %s", self.root_path)

        self.symbols = {}
        if self.workspace:
            file_paths = self.workspace.list_files("src", "*.py")
            if not file_paths:
                logger.warning("No source files found in workspace")
                return {"metadata": {}, "symbols": {}}
            for rel_path in file_paths:
                self._scan_file(self.root_path / rel_path)
        else:
            if not self.src_dir.exists():
                logger.warning("Source directory not found: %s", self.src_dir)
                return {"metadata": {}, "symbols": {}}

            for py_file in self.src_dir.rglob("*.py"):
                self._scan_file(py_file)

        return {
            "metadata": {
                "generated_at": datetime.now(UTC).isoformat(),
                "repo_root": str(self.root_path),
                "symbol_count": len(self.symbols),
            },
            "symbols": self.symbols,
        }

    def _scan_file(self, file_path: Path) -> None:
        """Scan a single Python file and add its symbols to the graph."""
        try:
            rel_path = file_path.relative_to(self.root_path)
        except ValueError:
            rel_path = file_path

        try:
            if self.workspace:
                content = self.workspace.read_text(rel_path.as_posix())
            else:
                content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            source_lines = content.splitlines()
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    self._process_symbol(node, file_path, source_lines)
        except Exception as exc:
            logger.error("Failed to process file %s: %s", file_path, exc)

    def _determine_domain(self, file_path: Path) -> str:
        """Determine the architectural domain of a file."""
        try:
            rel_path = file_path.relative_to(self.root_path)
        except ValueError:
            rel_path = file_path

        parts = rel_path.parts
        if "features" in parts:
            idx = parts.index("features")
            if idx + 1 < len(parts):
                candidate = parts[idx + 1]
                if not candidate.endswith(".py"):
                    return candidate

        abs_file_path = file_path.resolve()
        for domain_path, domain_name in self.domain_map.items():
            if str(abs_file_path).startswith(str(Path(domain_path).resolve())):
                return domain_name

        return "unknown"

    def _process_symbol(
        self, node: ast.AST, file_path: Path, source_lines: list[str]
    ) -> None:
        """Extract metadata for a symbol."""
        if not hasattr(node, "name"):
            return

        rel_path = file_path.relative_to(self.root_path)
        symbol_path_key = f"{rel_path}::{node.name}"

        metadata = parse_metadata_comment(node, source_lines)
        docstring = (extract_docstring(node) or "").strip()

        call_visitor = FunctionCallVisitor()
        call_visitor.visit(node)

        symbol_data = {
            "uuid": symbol_path_key,
            "key": metadata.get("capability"),
            "symbol_path": symbol_path_key,
            "name": node.name,
            "type": type(node).__name__,
            "file_path": str(rel_path),
            "domain": self._determine_domain(file_path),
            "is_public": not node.name.startswith("_"),
            "title": node.name.replace("_", " ").title(),
            "description": docstring.split("\n")[0] if docstring else None,
            "docstring": docstring,
            "calls": sorted(set(call_visitor.calls)),
            "line_number": node.lineno,
            "end_line_number": getattr(node, "end_lineno", node.lineno),
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "parameters": extract_parameters(node) if hasattr(node, "args") else [],
            "is_class": isinstance(node, ast.ClassDef),
            "base_classes": (
                extract_base_classes(node) if isinstance(node, ast.ClassDef) else []
            ),
            "structural_hash": calculate_structural_hash(node),
        }
        self.symbols[symbol_path_key] = symbol_data
