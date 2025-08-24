# src/core/knowledge_service.py
"""
Provides a runtime service for agents to query the system's knowledge graph for capabilities and self-knowledge.
"""

from __future__ import annotations

# src/core/knowledge_service.py
"""
Provides a runtime service for agents to query the system's
self-knowledge from the Knowledge Graph.
"""
from pathlib import Path
from typing import Any, Dict, List, Set

from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


class KnowledgeService:
    """A read-only service to access the system's knowledge graph."""

    def __init__(self, repo_path: Path):
        """Initializes the service and loads the knowledge graph."""
        self.knowledge_graph_path = (
            repo_path / ".intent" / "knowledge" / "knowledge_graph.json"
        )
        self.graph: Dict[str, Any] = {}
        self.load_graph()

    def load_graph(self):
        """Loads or reloads the knowledge graph from disk."""
        if not self.knowledge_graph_path.exists():
            log.warning("Knowledge graph not found. Introspection may be needed.")
            self.graph = {}
        else:
            self.graph = load_config(self.knowledge_graph_path, "json")
            log.info("Knowledge Service loaded the knowledge graph successfully.")

    def list_capabilities(self) -> List[str]:
        """Returns a sorted list of all unique, declared capabilities."""
        symbols = self.graph.get("symbols", {}).values()
        capabilities: Set[str] = {
            s["capability"]
            for s in symbols
            if s.get("capability") and s.get("capability") != "unassigned"
        }
        return sorted(list(capabilities))
