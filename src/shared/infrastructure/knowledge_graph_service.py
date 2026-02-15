# src/shared/infrastructure/knowledge_graph_service.py

"""
Knowledge Graph Builder - Sensory-Aware Logic Service.

Introspects the codebase and creates an in-memory representation of symbols.

UPGRADED: Accepts an optional LimbWorkspace to build a "Shadow Graph" of
uncommitted changes (Future Truth) combined with the base repository
(Historical Truth).

Constitutional Alignment:
- Pillar I (Octopus): Distributed sensation - the graph "tastes" the Crate.
- Pillar II (UNIX): Stateless fact extraction.
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


# ID: 8052e09f-edbb-4de2-974e-efcfbb139b32
class KnowledgeGraphBuilder:
    """
    Scans source code to build a comprehensive in-memory knowledge graph.

    Supports virtualized sensation via LimbWorkspace to prevent
    "Semantic Blindness" during autonomous refactoring.
    """

    def __init__(self, root_path: Path, workspace: LimbWorkspace | None = None) -> None:
        """
        Initialize the builder.

        Args:
            root_path: Path to the repository root.
            workspace: Optional LimbWorkspace providing a virtualized overlay of
                      uncommitted changes.
        """
        self.root_path = root_path.resolve()
        self.intent_dir = self.root_path / ".intent"
        self.src_dir = self.root_path / "src"
        self.workspace = workspace

        self.symbols: dict[str, dict[str, Any]] = {}
        self.domain_map = self._load_domain_map()
        self.entry_point_patterns = self._load_entry_point_patterns()

    def _load_domain_map(self) -> dict[str, str]:
        """Loads the architectural domain map from the constitution."""
        try:
            structure: dict[str, Any] | None = None

            # Prefer workspace overlay to allow refactor-time domain boundary changes.
            rel_path = ".intent/mind/knowledge/source_structure.yaml"
            if self.workspace and self.workspace.exists(rel_path):
                content = self.workspace.read_text(rel_path)
                structure = yaml.safe_load(content) or {}

            if structure is None:
                structure_path = (
                    self.intent_dir / "mind" / "knowledge" / "source_structure.yaml"
                )
                if not structure_path.exists():
                    structure_path = (
                        self.intent_dir
                        / "mind"
                        / "knowledge"
                        / "project_structure.yaml"
                    )

                if structure_path.exists():
                    structure = (
                        yaml.safe_load(structure_path.read_text(encoding="utf-8")) or {}
                    )
                else:
                    return {}

            items = (
                structure.get("structure", [])
                or structure.get("architectural_domains", [])
                or []
            )
            domain_map: dict[str, str] = {}

            for d in items:
                if not isinstance(d, dict):
                    continue
                if "path" not in d or "domain" not in d:
                    continue

                raw_path = str(d.get("path", ""))
                # Normalize "src/..." entries to be relative to src_dir.
                normalized = (
                    raw_path.replace("src/", "", 1)
                    if raw_path.startswith("src/")
                    else raw_path
                )
                abs_prefix = (self.src_dir / normalized).resolve()
                domain_map[str(abs_prefix)] = str(d.get("domain"))

            return domain_map

        except Exception as e:
            logger.warning("Failed to load domain map: %s", e)
            return {}

    def _load_entry_point_patterns(self) -> list[dict[str, Any]]:
        """Loads the patterns for identifying system entry points."""
        patterns_path_rel = ".intent/mind/knowledge/entry_point_patterns.yaml"
        try:
            if self.workspace and self.workspace.exists(patterns_path_rel):
                content = self.workspace.read_text(patterns_path_rel)
                patterns = yaml.safe_load(content) or {}
                return patterns.get("patterns", []) or []

            patterns_path = self.root_path / patterns_path_rel
            if patterns_path.exists():
                patterns = (
                    yaml.safe_load(patterns_path.read_text(encoding="utf-8")) or {}
                )
                return patterns.get("patterns", []) or []
        except Exception:
            # Patterns are optional; ignore failures.
            return []

        return []

    # ID: 4b979a4f-4eb6-4104-929b-c83b72b744e5
    # ID: df77032e-a986-4846-8c38-9849daabe695
    def build(self) -> dict[str, Any]:
        """
        Executes the full scan and returns the in-memory graph.

        If a workspace is present, it builds a "Shadow Graph" that merges
        uncommitted changes with the existing codebase.
        """
        mode = "SHADOW" if self.workspace else "STANDARD"
        logger.info("Building knowledge graph (%s mode) for: %s", mode, self.root_path)

        self.symbols = {}

        # 1) Determine which files to scan
        if self.workspace:
            # Sensation: unified list of virtual + physical files (relative paths expected).
            files_to_scan = self.workspace.list_files(directory="src", pattern="*.py")
        else:
            # Historical fallback: direct disk I/O
            if not self.src_dir.exists():
                logger.warning("Source directory not found: %s", self.src_dir)
                return {"metadata": {}, "symbols": {}}

            files_to_scan = [
                str(p.relative_to(self.root_path)) for p in self.src_dir.rglob("*.py")
            ]

        # 2) Perform the scan
        for rel_path in files_to_scan:
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
        """Scans a file using the sensory overlay (workspace if available)."""
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

        except Exception as e:
            logger.error("Failed to process file %s: %s", rel_path, e)

    def _determine_domain(self, file_path: Path) -> str:
        """Determines the architectural domain of a file (file_path is relative to root)."""
        abs_file_path = (self.root_path / file_path).resolve()

        # Heuristic: src/features/<domain>/...
        parts = file_path.parts
        if "features" in parts:
            idx = parts.index("features")
            if idx + 1 < len(parts):
                candidate = parts[idx + 1]
                if candidate and not candidate.endswith(".py"):
                    return candidate

        # Constitution-driven mapping (prefix match)
        for domain_path, domain_name in self.domain_map.items():
            try:
                if str(abs_file_path).startswith(str(Path(domain_path).resolve())):
                    return domain_name
            except Exception:
                continue

        return "unknown"

    def _process_symbol(
        self, node: ast.AST, rel_path: Path, source_lines: list[str]
    ) -> None:
        """Extracts metadata for a symbol."""
        name = getattr(node, "name", None)
        if not isinstance(name, str) or not name:
            return

        symbol_path_key = f"{rel_path.as_posix()}::{name}"

        metadata = parse_metadata_comment(node, source_lines) or {}
        docstring = (extract_docstring(node) or "").strip()

        call_visitor = FunctionCallVisitor()
        try:
            call_visitor.visit(node)
        except Exception:
            # Visitor should be best-effort; do not block symbol extraction.
            pass

        symbol_data: dict[str, Any] = {
            "uuid": symbol_path_key,
            "key": metadata.get("capability"),
            "symbol_path": symbol_path_key,
            "name": name,
            "type": type(node).__name__,
            "file_path": rel_path.as_posix(),
            "domain": self._determine_domain(rel_path),
            "is_public": not name.startswith("_"),
            "title": name.replace("_", " ").title(),
            "description": docstring.split("\n")[0] if docstring else None,
            "docstring": docstring,
            "calls": sorted(set(getattr(call_visitor, "calls", []) or [])),
            "line_number": getattr(node, "lineno", 0),
            "end_line_number": getattr(node, "end_lineno", getattr(node, "lineno", 0)),
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "parameters": extract_parameters(node) if hasattr(node, "args") else [],
            "is_class": isinstance(node, ast.ClassDef),
            "base_classes": (
                extract_base_classes(node) if isinstance(node, ast.ClassDef) else []
            ),
            "structural_hash": calculate_structural_hash(node),
        }

        self.symbols[symbol_path_key] = symbol_data
