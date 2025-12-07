# src/features/introspection/knowledge_graph_service.py

"""
Provides the KnowledgeGraphBuilder, the primary tool for introspecting the
codebase and creating an in-memory representation of its symbols.
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from shared.ast_utility import (
    FunctionCallVisitor,
    calculate_structural_hash,
    extract_base_classes,
    extract_docstring,
    extract_parameters,
    parse_metadata_comment,
)
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2e165ce4-0685-4157-b1da-89fdc2caa5f2
class KnowledgeGraphBuilder:
    """
    Scans the source code to build a comprehensive in-memory knowledge graph.
    It does not interact with the database; that is handled by the sync_service.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.intent_dir = self.root_path / ".intent"
        self.src_dir = self.root_path / "src"
        self.symbols: dict[str, dict[str, Any]] = {}
        self.domain_map = self._load_domain_map()
        self.entry_point_patterns = self._load_entry_point_patterns()

    def _load_domain_map(self) -> dict[str, str]:
        """Loads the architectural domain map from the constitution."""
        try:
            structure_path = (
                self.intent_dir / "mind" / "knowledge" / "source_structure.yaml"
            )
            structure = yaml.safe_load(structure_path.read_text("utf-8"))
            return {
                str(self.src_dir / d.get("path", "").replace("src/", "")): d["domain"]
                for d in structure.get("structure", [])
            }
        except (FileNotFoundError, yaml.YAMLError, KeyError):
            return {}

    def _load_entry_point_patterns(self) -> list[dict[str, Any]]:
        """Loads the declarative patterns for identifying system entry points."""
        try:
            patterns_path = (
                self.intent_dir / "mind" / "knowledge" / "entry_point_patterns.yaml"
            )
            patterns = yaml.safe_load(patterns_path.read_text("utf-8"))
            return patterns.get("patterns", [])
        except (FileNotFoundError, yaml.YAMLError):
            return []

    # ID: bd4866df-2036-4de5-ba12-781dd867fbdf
    def build(self) -> dict[str, Any]:
        """
        Executes the full build process for the knowledge graph and returns it.
        """
        logger.info(f"Building knowledge graph for repository at: {self.root_path}")
        for py_file in self.src_dir.rglob("*.py"):
            self._scan_file(py_file)
        knowledge_graph = {
            "metadata": {
                "generated_at": datetime.now(UTC).isoformat(),
                "repo_root": str(self.root_path),
            },
            "symbols": self.symbols,
        }
        output_path = settings.REPO_PATH / "reports" / "knowledge_graph.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(knowledge_graph, indent=2))
        logger.info(
            f"Knowledge graph artifact with {len(self.symbols)} symbols saved to {output_path}"
        )
        return knowledge_graph

    def _scan_file(self, file_path: Path):
        """Scans a single Python file and adds its symbols to the graph."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            source_lines = content.splitlines()
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    self._process_symbol(node, file_path, source_lines)
        except Exception as e:
            logger.error("Failed to process file {file_path}: %s", e)

    def _determine_domain(self, file_path: Path) -> str:
        """Determines the architectural domain of a file."""
        abs_file_path = file_path.resolve()
        for domain_path, domain_name in self.domain_map.items():
            if str(abs_file_path).startswith(str(Path(domain_path).resolve())):
                return domain_name
        return "unknown"

    def _process_symbol(self, node: ast.AST, file_path: Path, source_lines: list[str]):
        """Extracts all relevant data from a symbol AST node."""
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
            "is_public": not node.name.startswith("_"),
            "title": node.name.replace("_", " ").title(),
            "description": docstring.split("\n")[0] if docstring else None,
            "docstring": docstring,
            "calls": sorted(list(set(call_visitor.calls))),
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
