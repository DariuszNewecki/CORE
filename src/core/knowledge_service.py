# src/core/knowledge_service.py
"""
Centralized access to CORE's knowledge graph and declared capabilities from the database SSOT.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from services.database.session_manager import get_session
from shared.logger import getLogger
from sqlalchemy import text

log = getLogger("knowledge_service")


# ID: f1abb440-15b4-41b7-b36e-e63621c6d332
class KnowledgeService:
    """
    A read-only interface to the knowledge graph, which is sourced exclusively
    from the operational database view `core.knowledge_graph`.
    """

    def __init__(self, repo_path: Path | str = "."):
        self.repo_path = Path(repo_path)
        # The internal cache (`self._graph`) has been removed to enforce SSOT.

    # ID: 49190ab5-945a-4aa8-9500-21b849f217f9
    async def get_graph(self) -> Dict[str, Any]:
        """
        Loads the knowledge graph directly from the database, treating it as the
        single source of truth on every call. Caching is removed to ensure freshness.
        """
        log.info("Loading knowledge graph from database view...")
        symbols_map = {}
        try:
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM core.knowledge_graph ORDER BY symbol_path")
                )
                for row in result:
                    row_dict = dict(row._mapping)
                    symbol_path = row_dict.get("symbol_path")
                    if symbol_path:
                        # Ensure all UUIDs are converted to strings for consistent use.
                        if "uuid" in row_dict and row_dict["uuid"] is not None:
                            row_dict["uuid"] = str(row_dict["uuid"])
                        if (
                            "vector_id" in row_dict
                            and row_dict["vector_id"] is not None
                        ):
                            row_dict["vector_id"] = str(row_dict["vector_id"])
                        symbols_map[symbol_path] = row_dict

            knowledge_graph = {"symbols": symbols_map}
            log.info(
                f"Successfully loaded {len(symbols_map)} symbols from the database."
            )
            return knowledge_graph

        except Exception as e:
            log.error(
                f"Failed to load knowledge graph from database: {e}", exc_info=True
            )
            # Fallback to an empty graph to prevent crashing.
            return {"symbols": {}}

    # ID: 884e9a28-255c-478c-8af9-46865e45a029
    async def list_capabilities(self) -> List[str]:
        """Returns all capability keys directly from the database."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name FROM core.capabilities ORDER BY name")
            )
            return [row[0] for row in result]

    # ID: 9fa22aa4-5c09-46f7-a19c-c29851c92437
    async def search_capabilities(self, query: str, limit: int = 5) -> List[str]:
        """
        This is a placeholder. Real semantic search happens in CognitiveService.
        """
        all_caps = await self.list_capabilities()
        q_lower = query.lower()
        return [c for c in all_caps if q_lower in c.lower()][:limit]
