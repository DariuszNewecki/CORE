# src/body/introspection/knowledge_graph_service.py
# ID: 66489cb7-ecc7-4d3d-8e31-0e93d159458c

"""
Knowledge Graph Builder - Sensory-Aware logic service.
UPDATED: Domain heuristics adapted for layered architecture (Wave 3).
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


# ID: 322f2e00-3996-4c30-8bc6-ec9291be777c
class KnowledgeGraphBuilder:
    """
    Scan source code to build a comprehensive in-memory knowledge graph.
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
        """Load the architectural domain map."""
        try:
            rel_path = ".intent/mind/knowledge/source_structure.yaml"
            structure = None

            if self.workspace and self.workspace.exists(rel_path):
                content = self.workspace.read_text(rel_path)
                structure = yaml.safe_load(content) or {}
            else:
                path = self.intent_dir / "mind" / "knowledge" / "source_structure.yaml"
                if not path.exists():
                    path = (
                        self.intent_dir
                        / "mind"
                        / "knowledge"
                        / "project_structure.yaml"
                    )

                if path.exists():
                    structure = yaml.safe_load(path.read_text("utf-8")) or {}

            if structure:
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
        """Load entry point patterns."""
        try:
            rel_path = ".intent/mind/knowledge/entry_point_patterns.yaml"
            content = None

            if self.workspace and self.workspace.exists(rel_path):
                content = self.workspace.read_text(rel_path)
            else:
                path = self.root_path / rel_path
                if path.exists():
                    content = path.read_text("utf-8")

            if content:
                data = yaml.safe_load(content) or {}
                return data.get("patterns", [])
            return []
        except Exception as exc:
            logger.warning("Failed to load entry point patterns: %s", exc)
            return []

    # ID: 75c969e0-5c7c-4f58-9a46-62815947d77a
    def build(self) -> dict[str, Any]:
        """
        Execute the full scan and return the in-memory graph.
        """
        mode = "SHADOW" if self.workspace else "STANDARD"
        logger.info("Building knowledge graph (%s mode) for: %s", mode, self.root_path)

        self.symbols = {}

        if self.workspace:
            files_to_scan = self.workspace.list_files(directory="src", pattern="*.py")
            for rel_path in files_to_scan:
                self._scan_file_v2(rel_path)
        else:
            if not self.src_dir.exists():
                logger.warning("Source directory not found: %s", self.src_dir)
                return {"metadata": {}, "symbols": {}}

            for py_file in self.src_dir.rglob("*.py"):
                rel_path = str(py_file.relative_to(self.root_path))
                self._scan_file_v2(rel_path)

        return {
            "metadata": {
                "generated_at": datetime.now(UTC).isoformat(),
                "repo_root": str(self.root_path),
                "symbol_count": len(self.symbols),
                "mode": mode,
            },
            "symbols": self.symbols,
        }

    def _scan_file_v2(self, rel_path: str) -> None:
        """Scan a file using the sensory overlay."""
        try:
            if self.workspace:
                content = self.workspace.read_text(rel_path)
            else:
                content = (self.root_path / rel_path).read_text(encoding="utf-8")

            tree = ast.parse(content, filename=rel_path)
            source_lines = content.splitlines()
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    self._process_symbol(node, Path(rel_path), source_lines)
        except Exception as exc:
            logger.error("Failed to process file %s: %s", rel_path, exc)

    def _determine_domain(self, file_path: Path) -> str:
        """Determine the architectural domain of a file."""
        abs_file_path = (self.root_path / file_path).resolve()

        # UPDATED HEURISTIC: Check new layered homes
        parts = file_path.parts
        # If path is src/layer/domain/...
        if len(parts) >= 3 and parts[0] == "src":
            # Example: src/body/self_healing/ -> domain is self_healing
            return parts[2]

        # Constitution-driven mapping
        for domain_path, domain_name in self.domain_map.items():
            if str(abs_file_path).startswith(str(Path(domain_path).resolve())):
                return domain_name

        return "unknown"

    def _process_symbol(
        self, node: ast.AST, rel_path: Path, source_lines: list[str]
    ) -> None:
        """Extract metadata for a symbol."""
        if not hasattr(node, "name"):
            return

        symbol_path_key = f"{rel_path.as_posix()}::{node.name}"

        metadata = parse_metadata_comment(node, source_lines)
        docstring = (extract_docstring(node) or "").strip()

        call_visitor = FunctionCallVisitor()
        try:
            call_visitor.visit(node)
        except Exception:
            pass

        symbol_data = {
            "uuid": symbol_path_key,
            "key": metadata.get("capability"),
            "symbol_path": symbol_path_key,
            "name": node.name,
            "type": type(node).__name__,
            "file_path": rel_path.as_posix(),
            "domain": self._determine_domain(rel_path),
            "is_public": not node.name.startswith("_"),
            "title": node.name.replace("_", " ").title(),
            "description": docstring.split("\n")[0] if docstring else None,
            "docstring": docstring,
            "calls": sorted(set(getattr(call_visitor, "calls", []))),
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
