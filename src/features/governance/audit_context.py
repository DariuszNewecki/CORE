# src/features/governance/audit_context.py
"""
Defines the AuditorContext, a central data object that provides a consistent
view of the project's constitution and state for all audit checks.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from core.knowledge_service import KnowledgeService
from shared.logger import getLogger

log = getLogger("audit_context")


# ID: 7b2396c3-96ae-4f5b-bd70-09ef50bdfea0
class AuditorContext:
    """
    A data class that loads and provides access to all constitutional
    artifacts needed by the auditor and its checks.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path.resolve()
        self.intent_path = self.repo_path / ".intent"
        self.mind_path = self.intent_path / "mind"
        self.charter_path = self.intent_path / "charter"
        self.src_dir: Path = self.repo_path / "src"

        # These can be loaded synchronously
        self.meta: Dict[str, Any] = self._load_yaml(self.intent_path / "meta.yaml")
        self.policies: Dict[str, Any] = self._load_policies()
        self.source_structure: Dict[str, Any] = self._load_yaml(
            self.mind_path / "knowledge" / "source_structure.yaml"
        )
        # Initialize knowledge graph components as empty; they will be loaded async
        self.knowledge_graph: Dict[str, Any] = {"symbols": {}}
        self.symbols_list: list = []
        self.symbols_map: dict = {}
        log.debug("AuditorContext initialized synchronously.")

    # ID: 2f3d6adb-6584-40de-8ae8-e7b8e983d470
    async def load_knowledge_graph(self):
        """Asynchronously loads the knowledge graph from the service."""
        log.debug("Asynchronously loading knowledge graph...")
        knowledge_service = KnowledgeService(self.repo_path)
        self.knowledge_graph = await knowledge_service.get_graph()
        self.symbols_list = list(self.knowledge_graph.get("symbols", {}).values())
        self.symbols_map = self.knowledge_graph.get("symbols", {})
        log.debug("Knowledge graph loaded.")

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Safely loads a single YAML file, returning an empty dict on failure."""
        if not path.exists():
            log.warning(f"Constitutional file not found: {path}")
            return {}
        try:
            return yaml.safe_load(path.read_text("utf-8")) or {}
        except (yaml.YAMLError, IOError) as e:
            log.error(f"Failed to load or parse YAML at {path}: {e}")
            return {}

    def _load_policies(self) -> Dict[str, Any]:
        """Loads all policy files from the charter into a dictionary."""
        policies_dir = self.charter_path / "policies"
        loaded_policies: Dict[str, Any] = {}
        if not policies_dir.is_dir():
            log.warning(f"Policies directory not found: {policies_dir}")
            return {}

        for policy_file in policies_dir.glob("**/*_policy.yaml"):
            policy_id = policy_file.stem
            policy_content = self._load_yaml(policy_file)
            if policy_content:
                loaded_policies[policy_id] = policy_content

        log.debug(f"Loaded {len(loaded_policies)} policies.")
        return loaded_policies

    @property
    # ID: ac544885-00f8-49d9-8aab-24c58947f6fc
    def python_files(self) -> list[Path]:
        """Get all Python files in the repository."""
        python_files = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [
                d
                for d in dirs
                if d
                not in {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv"}
            ]
            for file in files:
                if file.endswith(".py"):
                    python_files.append(Path(root) / file)
        return python_files
