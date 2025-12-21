# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.

CONSTITUTIONAL COMPLIANCE:
- Uses PathResolver for robust directory discovery (Constitution/Policies/Standards)
- Dynamically loads governance artifacts from the filesystem (SSOT: .intent/)
- Loads Knowledge Graph from Database (SSOT) via KnowledgeService
- Exposes legacy path attributes (mind_path, charter_path) for compatibility
- Gracefully handles missing deprecated project_structure.yaml (db.cli_registry_in_db)
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
    and prioritizes canonical intent layout as SSOT.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.meta: dict[str, Any] = settings._meta_config
        self.paths = PathResolver(repo_path, self.meta)
        self.src_dir = self.paths.repo_root / "src"
        self.intent_path = self.paths.intent_root
        self.last_findings: list[AuditFinding] = []

        # Governance resources (policies/standards/constitution) loaded from filesystem
        self.policies: dict[str, Any] = self._load_governance_resources()

        # CONSTITUTIONAL FIX: Graceful handling of deprecated project_structure.yaml
        # This file is being migrated to database (db.cli_registry_in_db rule)
        structure_path = self.paths.mind_root / "knowledge/project_structure.yaml"
        if structure_path.exists():
            self.source_structure = strict_yaml_processor.load_strict(structure_path)
        else:
            logger.debug(
                "project_structure.yaml not found (deprecated), using empty structure"
            )
            self.source_structure = {}

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
        """Legacy accessor for .intent/charter directory (compat shim)."""
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
        Load governance resources from canonical intent layout.

        Canonical roots (SSOT):
          - .intent/policies      (primary; typically JSON)
          - .intent/standards     (optional; JSON/YAML)
          - .intent/constitution  (optional; JSON/YAML)

        Indexing strategy:
          - canonical_key: relative path under root, no extension (e.g. 'operations/safety')
          - stem: filename stem for legacy callers
          - internal ids: 'id' and 'policy_id' when present
        """
        resources: dict[str, Any] = {}

        # ID: 58adcf66-24b7-4f66-9d1a-efda298c95ac
        def iter_intent_files(root: Path) -> list[Path]:
            files: list[Path] = []
            if not root.exists():
                return files
            files.extend([p for p in root.rglob("*.json") if p.is_file()])
            files.extend([p for p in root.rglob("*.yaml") if p.is_file()])
            files.extend([p for p in root.rglob("*.yml") if p.is_file()])
            return files

        # ID: 7cf3b7bc-0280-4f8d-8a75-06d127afdc86
        def canonical_key(root: Path, file_path: Path) -> str:
            rel = file_path.relative_to(root)
            return rel.with_suffix("").as_posix()

        # Prefer policies; then standards; then constitution (for checks that want it)
        search_roots: list[tuple[str, Path]] = [
            ("policies", self.paths.policies_dir),
            ("standards", self.paths.standards_root),
            ("constitution", self.paths.constitution_dir),
        ]

        files_loaded = 0
        for root_name, root in search_roots:
            for file_path in iter_intent_files(root):
                try:
                    data = strict_yaml_processor.load_strict(file_path)
                    if not isinstance(data, dict):
                        continue

                    key = canonical_key(root, file_path)
                    # Namespacing avoids collisions between policies vs standards vs constitution
                    namespaced_key = f"{root_name}/{key}"

                    # Canonical handles
                    resources[namespaced_key] = data
                    resources[key] = data  # legacy-ish, but still useful in many checks
                    resources[file_path.stem] = data

                    # Internal ids (common in your policy docs)
                    doc_id = data.get("id")
                    if isinstance(doc_id, str) and doc_id:
                        resources[doc_id] = data
                    policy_id = data.get("policy_id")
                    if isinstance(policy_id, str) and policy_id:
                        resources[policy_id] = data

                    files_loaded += 1
                except Exception as e:
                    logger.debug(
                        "Skipping unparseable governance file %s: %s", file_path.name, e
                    )

        if files_loaded == 0:
            logger.warning(
                "No governance resources found under .intent/(policies|standards|constitution)."
            )
        else:
            logger.info(
                "Loaded %s governance resource file(s) from .intent/", files_loaded
            )

        return resources

    @property
    # ID: 39d97b4e-5d44-4e43-8ccc-d194f851c62c
    def python_files(self) -> list[Path]:
        """Returns Python files ONLY from BODY (src/)."""
        paths: list[Path] = []
        if self.src_dir.exists():
            paths.extend(self.src_dir.rglob("*.py"))
        return list(paths)


__all__ = ["AuditorContext"]
