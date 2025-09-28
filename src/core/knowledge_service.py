# src/core/knowledge_service.py
"""
Centralized access to CORE's knowledge graph and declared capabilities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from shared.logger import getLogger

log = getLogger(__name__)


# ID: 037d06d1-8f6d-4347-83b4-fba15da40639
class KnowledgeService:
    """
    Lightweight wrapper for loading the knowledge graph and capabilities
    from the repository. Designed to be easily mockable in tests.
    """

    def __init__(self, repo_path: Path | str = "."):
        self.repo_path = Path(repo_path)
        self._graph: Dict[str, Any] | None = None
        self._capabilities_cache: List[str] | None = None

    # ---------------- Public API ----------------

    # ID: 7a219e96-6846-49ff-95fe-596a0429447c
    async def get_graph(self) -> Dict[str, Any]:
        """
        Loads (or returns cached) knowledge graph structure.
        Keep this fast and forgiving for tests/integration.
        """
        if self._graph is not None:
            return self._graph

        graph_file_paths = [
            self.repo_path / ".intent/mind/knowledge/graph.yaml",
            self.repo_path / ".intent/mind/knowledge/graph.yml",
        ]

        for p in graph_file_paths:
            if p.exists():
                try:
                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                    if not isinstance(data, dict):
                        log.warning("Knowledge graph YAML is not a mapping: %s", p)
                        data = {}
                    self._graph = data
                    return self._graph
                except Exception as e:  # noqa: BLE001
                    log.error("Failed to load knowledge graph from %s: %s", p, e)
                    break

        # Fallback to empty graph (tests often mock specific methods)
        self._graph = {}
        return self._graph

    # ID: 0e38c18e-2a3d-47cb-bf77-4b4d9bf5354a
    async def list_capabilities(self) -> List[str]:
        """
        Returns declared capability keys.
        Tests patch this method; default implementation reads YAML if present.
        """
        if self._capabilities_cache is not None:
            return self._capabilities_cache

        caps_file_paths = [
            self.repo_path / ".intent/mind/knowledge/capabilities.yaml",
            self.repo_path / ".intent/mind/knowledge/capabilities.yml",
        ]

        for p in caps_file_paths:
            if p.exists():
                try:
                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
                    if isinstance(data, dict) and "capabilities" in data:
                        data = data.get("capabilities", [])
                    if not isinstance(data, list):
                        log.warning("Capabilities YAML is not a list: %s", p)
                        data = []
                    # Normalize to list[str]
                    self._capabilities_cache = [str(x) for x in data]
                    return self._capabilities_cache
                except Exception as e:  # noqa: BLE001
                    log.error("Failed to load capabilities from %s: %s", p, e)
                    break

        self._capabilities_cache = []
        return self._capabilities_cache

    # ID: d93ecbdb-f832-4539-9a79-74fcbe723ac3
    async def search_capabilities(self, query: str, limit: int = 5) -> List[str]:
        """
        Super-simple substring search over capability keys.
        Sufficient for the /knowledge/search endpoint unless replaced with vector search.
        """
        caps = await self.list_capabilities()
        q = query.lower().strip()
        if not q:
            return []
        results = [c for c in caps if q in c.lower()]
        return results[: max(1, min(limit, 50))]
