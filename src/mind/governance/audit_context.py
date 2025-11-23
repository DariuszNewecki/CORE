# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.knowledge.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding

logger = getLogger(__name__)


# ID: 2dc8a2b7-b3f7-4050-bb95-8e3f1648d419
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.
    This version is constitutionally-aware and loads policies via meta.yaml.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.intent_path = settings.MIND
        self.mind_path = settings.MIND / "mind"
        self.charter_path = settings.MIND / "charter"
        self.src_dir = settings.BODY / "src"
        self.last_findings: list[AuditFinding] = []
        self.meta: dict[str, Any] = settings._meta_config
        self.policies: dict[str, Any] = self._load_policies()
        self.source_structure: dict[str, Any] = settings.load(
            "mind.knowledge.project_structure"
        )
        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list = []
        self.symbols_map: dict = {}
        logger.debug("AuditorContext initialized.")

    # ID: b6970345-7493-4c25-abe6-0fdaf3143e14
    async def load_knowledge_graph(self) -> None:
        """Load the knowledge graph from the service (async)."""
        service = KnowledgeService(self.repo_path)
        self.knowledge_graph = await service.get_graph()
        self.symbols_map = self.knowledge_graph.get("symbols", {})
        self.symbols_list = list(self.symbols_map.values())
        logger.info(f"Loaded knowledge graph with {len(self.symbols_list)} symbols.")

    def _load_policies(self) -> dict[str, Any]:
        """
        Loads all policy files as defined in the meta.yaml index.
        This is the new, constitutionally-aware method.
        """
        policies_to_load = settings._meta_config.get("charter", {}).get("policies", {})
        if not policies_to_load:
            logger.warning("No policies are defined in meta.yaml.")
            return {}
        loaded_policies: dict[str, Any] = {}
        for logical_name, file_rel_path in policies_to_load.items():
            try:
                logical_path = f"charter.policies.{logical_name}"
                loaded_policies[logical_name] = settings.load(logical_path)
            except (FileNotFoundError, OSError, ValueError) as e:
                logger.error(
                    f"Failed to load constitutionally-defined policy '{logical_name}': {e}"
                )
                loaded_policies[logical_name] = {}
        return loaded_policies

    @property
    # ID: 38c486bf-9050-4814-b665-188118e16114
    def python_files(self) -> list[Path]:
        """Returns Python files ONLY from BODY (src/)."""
        paths: list[Path] = []
        for file_path in self.src_dir.rglob("*.py"):  # ← Scan ONLY BODY!
            paths.append(file_path)
        return paths


__all__ = ["AuditorContext"]
