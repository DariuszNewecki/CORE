# src/core/knowledge_service.py
"""
Provides a runtime service for agents to query the system's knowledge graph
from the database, which is the single source of truth.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Set

from sqlalchemy import text

from services.repositories.db.engine import get_session
from shared.logger import getLogger

log = getLogger(__name__)


# ID: 2ea793f9-c474-4de2-b41d-4c6a2d1f5646
class KnowledgeService:
    """A read-only service to access the system's knowledge graph from the database."""

    def __init__(self, repo_path: Path):
        """Initializes the service."""
        self.repo_path = repo_path
        self._graph: Dict[str, Any] | None = None
        self._graph_load_lock = asyncio.Lock()
        log.info("KnowledgeService initialized.")

    # ID: 67d7ea3f-672b-40d7-8362-be4735081420
    async def get_graph(self) -> Dict[str, Any]:
        """
        Lazily loads the knowledge graph from the database on first access.
        This method is now the primary async entry point for getting graph data.
        """
        if self._graph is None:
            async with self._graph_load_lock:
                # Double-check lock to prevent race conditions
                if self._graph is None:
                    log.info("Knowledge graph not loaded, fetching from database...")
                    self._graph = await self._get_graph_from_db()
        return self._graph

    async def _get_graph_from_db(self) -> Dict[str, Any]:
        """
        Fetches the knowledge graph from the database view and reconstructs it
        into the dictionary format expected by the system.
        """
        symbols_map: Dict[str, Any] = {}
        try:
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM core.knowledge_graph")
                )
                for row in result:
                    row_dict = dict(row._mapping)
                    symbols_map[row_dict["symbol_path"]] = row_dict
        except Exception as e:
            log.error(f"Failed to load knowledge graph from database: {e}")
            return {"symbols": {}}

        log.info(f"Successfully loaded {len(symbols_map)} symbols from database.")
        return {"symbols": symbols_map}

    # ID: 53b1bc81-af62-45f3-b6e4-b18e328ef088
    async def list_capabilities(self) -> List[str]:
        """Returns a sorted list of all unique, declared capabilities."""
        graph = await self.get_graph()
        symbols = graph.get("symbols", {}).values()
        capabilities: Set[str] = {
            s["capability"]
            for s in symbols
            if s.get("capability") and s.get("capability") != "unassigned"
        }
        return sorted(list(capabilities))
