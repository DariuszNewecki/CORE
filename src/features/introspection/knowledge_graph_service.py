# src/features/introspection/knowledge_graph_service.py
"""
Provides the KnowledgeGraphBuilder, the primary tool for introspecting the
codebase and synchronizing the discovered knowledge with the database.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml
from services.repositories.db.engine import get_session
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
from sqlalchemy import text

log = getLogger("knowledge_graph_builder")


# ID: 64fe527b-e2ab-4232-9a54-1a24d17a6ff1
class KnowledgeGraphBuilder:
    """
    Scans the source code to build a comprehensive knowledge graph and syncs it
    to the operational database.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.intent_dir = self.root_path / ".intent"
        self.src_dir = self.root_path / "src"
        self.symbols: Dict[str, Dict[str, Any]] = {}
        self.domain_map = self._load_domain_map()
        self.entry_point_patterns = self._load_entry_point_patterns()

    def _load_domain_map(self) -> Dict[str, str]:
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

    def _load_entry_point_patterns(self) -> List[Dict[str, Any]]:
        """Loads the declarative patterns for identifying system entry points."""
        try:
            patterns_path = (
                self.intent_dir / "mind" / "knowledge" / "entry_point_patterns.yaml"
            )
            patterns = yaml.safe_load(patterns_path.read_text("utf-8"))
            return patterns.get("patterns", [])
        except (FileNotFoundError, yaml.YAMLError):
            return []

    async def _sync_symbols_to_db(self, symbols: List[Dict]):
        """Performs a TRUNCATE and INSERT to sync symbols to the database."""
        if not symbols:
            return

        async with get_session() as session:
            async with session.begin():
                await session.execute(text("TRUNCATE TABLE core.symbols CASCADE"))
                await session.execute(
                    text(
                        """
                        INSERT INTO core.symbols (uuid, key, symbol_path, file_path, is_public, title, description, owner, status, structural_hash)
                        VALUES (:uuid, :key, :symbol_path, :file_path, :is_public, :title, :description, 'unassigned_agent', 'active', :structural_hash)
                    """
                    ),
                    symbols,
                )
        log.info(f"Successfully synced {len(symbols)} symbols to the database.")

    # ID: 6de62bc4-767f-4bc1-b5f1-25ee31af1009
    async def build_and_sync(self) -> Dict[str, Any]:  # <-- NOW ASYNC
        """
        Executes the full build and sync process for the knowledge graph.
        """
        log.info(f"Building knowledge graph for repository at: {self.root_path}")
        for py_file in self.src_dir.rglob("*.py"):
            self._scan_file(py_file)

        # Sync to database
        await self._sync_symbols_to_db(list(self.symbols.values()))  # <-- NOW AWAITED

        knowledge_graph = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "repo_root": str(self.root_path),
            },
            "symbols": self.symbols,
        }

        output_path = settings.REPO_PATH / "reports" / "knowledge_graph.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(knowledge_graph, indent=2))
        log.info(
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
            log.error(f"Failed to process file {file_path}: {e}")

    def _determine_domain(self, file_path: Path) -> str:
        """Determines the architectural domain of a file."""
        abs_file_path = file_path.resolve()
        for domain_path, domain_name in self.domain_map.items():
            if str(abs_file_path).startswith(str(Path(domain_path).resolve())):
                return domain_name
        return "unknown"

    def _process_symbol(self, node: ast.AST, file_path: Path, source_lines: List[str]):
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
