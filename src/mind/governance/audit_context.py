# src/mind/governance/audit_context.py

"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
        # FIX: Derive paths from the provided repo_path, not global settings
        self.intent_path = self.repo_path / ".intent"
        self.mind_path = self.intent_path / "mind"
        self.charter_path = self.intent_path / "charter"
        self.src_dir = self.repo_path / "src"

        self.last_findings: list[AuditFinding] = []

        # We still use settings for meta config structure as that shouldn't change between envs,
        # but we must ensure policy loading respects the new root.
        self.meta: dict[str, Any] = settings._meta_config
        self.policies: dict[str, Any] = self._load_policies()

        # Re-load project structure from the specific repo path if possible
        structure_path = self.mind_path / "knowledge/project_structure.yaml"
        if structure_path.exists():
            from shared.utils.yaml_processor import strict_yaml_processor

            self.source_structure = strict_yaml_processor.load_strict(structure_path)
        else:
            self.source_structure = settings.load("mind.knowledge.project_structure")

        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list = []
        self.symbols_map: dict = {}
        logger.debug(f"AuditorContext initialized for {self.repo_path}")

    # ID: b6970345-7493-4c25-abe6-0fdaf3143e14
    async def load_knowledge_graph(self) -> None:
        """
        Load the knowledge graph from the Filesystem via Builder.

        We use the Builder (AST scan) instead of the Service (DB) because this context
        might be running in a Canary environment where the code on disk differs
        from what is in the database.
        """
        from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder

        logger.info(f"Building fresh knowledge graph from files in {self.repo_path}...")
        builder = KnowledgeGraphBuilder(self.repo_path)

        # Run build synchronously as it is CPU bound (AST parsing)
        self.knowledge_graph = builder.build()

        self.symbols_map = self.knowledge_graph.get("symbols", {})
        self.symbols_list = list(self.symbols_map.values())
        logger.info(f"Loaded knowledge graph with {len(self.symbols_list)} symbols.")

    def _load_policies(self) -> dict[str, Any]:
        """
        Loads all policy files as defined in the meta.yaml index.
        Resolves paths relative to the current intent_path.
        """
        policies_to_load = settings._meta_config.get("charter", {}).get("policies", {})
        if not policies_to_load:
            logger.warning("No policies are defined in meta.yaml.")
            return {}

        loaded_policies: dict[str, Any] = {}
        from shared.utils.yaml_processor import strict_yaml_processor

        # Helper to flatten the policy map
        # ID: 4876c540-3d4c-4cb5-b3e2-a79cdc3c080a
        def flatten_dict(d, parent_key="", sep="."):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)

        flat_policies = flatten_dict(policies_to_load)

        for logical_name, file_rel_path in flat_policies.items():
            # Extract the simple name (last part) for the key
            simple_name = logical_name.split(".")[-1]

            try:
                # If path starts with charter/ or mind/, it is inside .intent
                full_path = self.intent_path / file_rel_path

                if full_path.exists():
                    loaded_policies[simple_name] = strict_yaml_processor.load_strict(
                        full_path
                    )
                else:
                    # Try relative to repo root just in case
                    full_path_repo = self.repo_path / file_rel_path
                    if full_path_repo.exists():
                        loaded_policies[simple_name] = (
                            strict_yaml_processor.load_strict(full_path_repo)
                        )
                    else:
                        # Fallback to settings if we can't find it locally (might be unchanged)
                        loaded_policies[simple_name] = settings.load(
                            f"charter.policies.{logical_name}"
                        )

            except (FileNotFoundError, OSError, ValueError) as e:
                logger.warning(
                    f"Failed to load policy '{logical_name}' in context: {e}"
                )
                loaded_policies[simple_name] = {}

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
