# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.

CONSTITUTIONAL COMPLIANCE FIX:
- Uses PathResolver for robust directory discovery (Constitution/Standards)
- Dynamically loads standards from the filesystem (ignoring outdated meta.yaml paths)
- Loads Knowledge Graph from Database (SSOT) via KnowledgeService
- Exposes legacy path attributes (mind_path, charter_path) for compatibility
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.models import AuditFinding
from shared.path_resolver import PathResolver
from shared.utils.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


# ID: 55a77b97-fc08-4b0c-b818-97b1158343e9
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.
    This version is constitutionally-aware, robust to directory restructuring,
    and prioritizes filesystem reality over outdated meta.yaml configuration.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.meta: dict[str, Any] = settings._meta_config
        self.paths = PathResolver(repo_path, self.meta)
        self.src_dir = self.paths.repo_root / "src"
        self.intent_path = self.paths.intent_root
        self.last_findings: list[AuditFinding] = []
        self.policies: dict[str, Any] = self._load_governance_resources()
        structure_path = self.paths.mind_root / "knowledge/project_structure.yaml"
        if structure_path.exists():
            self.source_structure = strict_yaml_processor.load_strict(structure_path)
        else:
            self.source_structure = settings.load("mind.knowledge.project_structure")
        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list = []
        self.symbols_map: dict = {}
        logger.debug("AuditorContext initialized for %s", self.repo_path)

    @property
    # ID: e6f262c9-0852-4d65-8fc7-c0a03808b3b7
    def mind_path(self) -> Path:
        """Legacy accessor for .intent/mind directory."""
        return self.paths.mind_root

    @property
    # ID: 3b95fd8e-69e9-4909-bbbd-bfc2f8c31c1e
    def charter_path(self) -> Path:
        """Legacy accessor for .intent/charter directory."""
        return self.paths.charter_root

    # ID: 090d1c13-3389-4f4c-81d0-eadf1c3259b2
    async def load_knowledge_graph(self) -> None:
        """
        Load the knowledge graph from the Database (SSOT).
        """
        logger.info(
            "Loading knowledge graph from database (SSOT) for %s...", self.repo_path
        )
        try:
            knowledge_service = KnowledgeService(self.repo_path)
            self.knowledge_graph = await knowledge_service.get_graph()
            self.symbols_map = self.knowledge_graph.get("symbols", {})
            self.symbols_list = list(self.symbols_map.values())
            logger.info(
                "Loaded knowledge graph with %s symbols from database.",
                len(self.symbols_list),
            )
            self._save_knowledge_graph_artifact()
        except Exception as e:
            logger.error("Failed to load knowledge graph from DB: %s", e)
            self.knowledge_graph = {"symbols": {}}

    def _save_knowledge_graph_artifact(self) -> None:
        """Save knowledge graph to reports/ for debugging."""
        import json

        reports_dir = self.paths.reports_dir
        reports_dir.mkdir(exist_ok=True)
        artifact_path = reports_dir / "knowledge_graph.json"
        try:
            with open(artifact_path, "w", encoding="utf-8") as f:
                json.dump(self.knowledge_graph, f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to save knowledge graph artifact: %s", e)

    def _load_governance_resources(self) -> dict[str, Any]:
        """
        Robustly load all governance resources (Policies & Standards).

        Strategy:
        1. Scan the new 'standards' directory (primary source).
        2. Scan the legacy 'policies' directory (if it exists).
        3. Index by both Filename (stem) and Internal ID.

        This overrides the brittle meta.yaml mapping.
        """
        resources: dict[str, Any] = {}
        search_roots = [self.paths.standards_root, self.paths.charter_root / "policies"]
        files_loaded = 0
        for root in search_roots:
            if not root.exists():
                continue
            for yaml_file in root.rglob("*.yaml"):
                try:
                    data = strict_yaml_processor.load_strict(yaml_file)
                    if not isinstance(data, dict):
                        continue
                    resources[yaml_file.stem] = data
                    if "id" in data:
                        resources[data["id"]] = data
                    if "policy_id" in data:
                        resources[data["policy_id"]] = data
                    files_loaded += 1
                except Exception as e:
                    logger.debug(
                        "Skipping unparseable governance file {yaml_file.name}: %s", e
                    )
        if files_loaded == 0:
            logger.warning("No governance policies/standards found in charter!")
        else:
            logger.info("Loaded %s governance resources.", files_loaded)
        return resources

    @property
    # ID: 39d97b4e-5d44-4e43-8ccc-d194f851c62c
    def python_files(self) -> list[Path]:
        """Returns Python files ONLY from BODY (src/)."""
        paths: list[Path] = []
        if self.src_dir.exists():
            for file_path in self.src_dir.rglob("*.py"):
                paths.append(file_path)
        return paths


__all__ = ["AuditorContext"]
