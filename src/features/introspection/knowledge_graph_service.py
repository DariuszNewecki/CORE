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


# ID: b64ba9c9-f55c-4a24-bc2d-d8c2fa04b43e
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
            # Tries to load source_structure.yaml first, often used for broad mapping
            structure_path = (
                self.intent_dir / "mind" / "knowledge" / "source_structure.yaml"
            )
            if not structure_path.exists():
                # Fallback to project_structure.yaml if source_structure is missing
                structure_path = (
                    self.intent_dir / "mind" / "knowledge" / "project_structure.yaml"
                )

            if structure_path.exists():
                structure = yaml.safe_load(structure_path.read_text("utf-8"))
                # If checking project_structure.yaml, keys might be under 'architectural_domains'
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
        except (yaml.YAMLError, KeyError, Exception) as e:
            logger.warning("Failed to load domain map: %s", e)
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

    # ID: 75c969e0-5c7c-4f58-9a46-62815947d77a
    def build(self) -> dict[str, Any]:
        """
        Executes the full build process for the knowledge graph and returns it.
        """
        logger.info("Building knowledge graph for repository at: %s", self.root_path)
        # Reset symbols on rebuild
        self.symbols = {}
        for py_file in self.src_dir.rglob("*.py"):
            self._scan_file(py_file)

        knowledge_graph = {
            "metadata": {
                "generated_at": datetime.now(UTC).isoformat(),
                "repo_root": str(self.root_path),
            },
            "symbols": self.symbols,
        }

        # Save artifact for reporting/debugging
        output_path = settings.REPO_PATH / "reports" / "knowledge_graph.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(knowledge_graph, indent=2))

        logger.info(
            "Knowledge graph artifact with %s symbols saved to %s",
            len(self.symbols),
            output_path,
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
            logger.error("Failed to process file %s: %s", file_path, e)

    def _determine_domain(self, file_path: Path) -> str:
        """
        Determines the architectural domain of a file.

        Logic:
        1. If inside `src/features/<subdir>`, the domain is <subdir>.
        2. Otherwise, falls back to the architectural domain map.
        """
        try:
            rel_path = file_path.relative_to(self.root_path)
        except ValueError:
            rel_path = file_path

        parts = rel_path.parts

        # 1. Feature Sub-domains (Priority for Operational Drift check)
        # Structure matches: src/features/<domain_name>/...
        # We look for index of 'features' and take the next part
        if "features" in parts:
            try:
                idx = parts.index("features")
                # Ensure there is a folder after 'features'
                if idx + 1 < len(parts):
                    candidate = parts[idx + 1]
                    # Exclude files directly in features/ like __init__.py
                    if not candidate.endswith(".py"):
                        return candidate
            except ValueError:
                pass

        # 2. Architectural Domains (Fallback from map)
        # This handles high-level domains like 'api', 'core', 'mind', 'shared'
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

        # Determine domain dynamically based on file location
        domain = self._determine_domain(file_path)

        symbol_data = {
            "uuid": symbol_path_key,
            # If # ID tag exists, use it as the primary key reference if needed,
            # though usually uuid field here is the path-key.
            # The SyncService often reconciles this with the # ID tag.
            "key": metadata.get("capability"),
            "symbol_path": symbol_path_key,
            "name": node.name,
            "type": type(node).__name__,
            "file_path": str(rel_path),
            "domain": domain,  # <--- CRITICAL FIX: Domain assignment
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
