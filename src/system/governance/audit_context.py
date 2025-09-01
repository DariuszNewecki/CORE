# src/system/governance/audit_context.py
"""
Shared context and state management for constitutional audit operations.

This module provides the AuditorContext class that encapsulates all shared state,
configuration, and resources needed by constitutional audit checks, including
repository paths, intent models, and knowledge graph data.
"""

from __future__ import annotations

from pathlib import Path

from core.intent_model import IntentModel
from shared.config_loader import load_config
from shared.utils.manifest_aggregator import aggregate_manifests


# CAPABILITY: system.audit.context
class AuditorContext:
    """Shared state container for audit checks."""

    # CAPABILITY: system.governance.audit_context.initialize
    def __init__(self, repo_root: Path):
        """
        Initialize context with repository paths and configurations.

        Args:
            repo_root: Root directory of the repository.
        """
        self.repo_root: Path = repo_root
        self.intent_dir: Path = repo_root / ".intent"
        self.src_dir: Path = repo_root / "src"
        self.intent_model = IntentModel(repo_root)
        self.project_manifest = aggregate_manifests(repo_root)
        self.knowledge_graph = load_config(
            self.intent_dir / "knowledge/knowledge_graph.json"
        )
        self.symbols_map: dict = self.knowledge_graph.get("symbols", {})
        self.symbols_list: list = list(self.symbols_map.values())
        self.load_config = load_config
