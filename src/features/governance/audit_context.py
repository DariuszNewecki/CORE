# src/features/governance/audit_context.py
"""
AuditorContext: central view of constitutional artifacts and the knowledge graph
for governance checks and audits.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from core.knowledge_service import KnowledgeService
from shared.logger import getLogger
from shared.models import AuditFinding

log = getLogger("audit_context")


# ID: 245a7de6-5465-41d2-a588-2da4cc86d72f
class AuditorContext:
    """
    Provides access to '.intent' artifacts and the in-memory knowledge graph.
    Tests import this symbol directly from features.governance.audit_context.
    """

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()
        self.intent_path = self.repo_path / ".intent"
        self.mind_path = self.intent_path / "mind"
        self.charter_path = self.intent_path / "charter"
        self.src_dir = self.repo_path / "src"

        # Optional: last audit results
        self.last_findings: list[AuditFinding] = []

        # Load constitutional data
        self.meta: dict[str, Any] = self._load_yaml(self.intent_path / "meta.yaml")
        self.policies: dict[str, Any] = self._load_policies()
        self.source_structure: dict[str, Any] = self._load_yaml(
            self.mind_path / "knowledge" / "source_structure.yaml"
        )

        # Knowledge graph placeholders
        self.knowledge_graph: dict[str, Any] = {"symbols": {}}
        self.symbols_list: list = []
        self.symbols_map: dict = {}

        log.debug("AuditorContext initialized.")

    # ID: d5feef3c-c5c7-4f3c-b940-46a154af4778
    async def load_knowledge_graph(self) -> None:
        """Load the knowledge graph from the service (async)."""
        service = KnowledgeService(self.repo_path)
        self.knowledge_graph = await service.get_graph()
        self.symbols_map = self.knowledge_graph.get("symbols", {})
        self.symbols_list = list(self.symbols_map.values())
        log.info(f"Loaded knowledge graph with {len(self.symbols_list)} symbols.")

    # -------------------- helpers -------------------- #

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            log.warning(f"YAML not found: {path}")
            return {}
        try:
            return yaml.safe_load(path.read_text("utf-8")) or {}
        except Exception as e:
            log.error(f"Failed to parse YAML {path}: {e}")
            return {}

    def _load_policies(self) -> dict[str, Any]:
        policies_dir = self.charter_path / "policies"
        if not policies_dir.is_dir():
            log.warning(f"Policies directory missing: {policies_dir}")
            return {}
        out: dict[str, Any] = {}
        for f in policies_dir.glob("**/*_policy.yaml"):
            content = self._load_yaml(f)
            if content:
                out[f.stem] = content
        return out

    @property
    # ID: 95118d68-5e7f-407c-9747-7cce100fe482
    def python_files(self) -> list[Path]:
        paths: list[Path] = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [
                d
                for d in dirs
                if d
                not in {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
            ]
            for name in files:
                if name.endswith(".py"):
                    paths.append(Path(root) / name)
        return paths


# Make the export explicit to avoid rare import edge cases in test boot
__all__ = ["AuditorContext"]
