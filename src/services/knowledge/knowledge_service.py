# src/services/knowledge/knowledge_service.py

"""
Centralized access to CORE's knowledge graph and declared capabilities from the database SSOT.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.database.session_manager import get_session
from shared.logger import getLogger
from sqlalchemy import text

logger = getLogger(__name__)


# ID: 0ea99489-3a7e-454e-b7d3-85da878b392d
class KnowledgeService:
    """
    A read-only interface to the knowledge graph, which is sourced exclusively
    from the operational database view `core.knowledge_graph`.
    """

    def __init__(self, repo_path: Path | str = ".", session=None):
        self.repo_path = Path(repo_path)
        self._session = session

    # ID: d20ec024-c182-4673-aff6-a5a38cb5f418
    async def get_graph(self) -> dict[str, Any]:
        """
        Loads the knowledge graph directly from the database, treating it as the
        single source of truth on every call. Caching is removed to ensure freshness.
        """
        logger.info("Loading knowledge graph from database view...")
        symbols_map = {}
        try:
            if self._session:
                result = await self._session.execute(
                    text("SELECT * FROM core.knowledge_graph ORDER BY symbol_path")
                )
                for row in result:
                    row_dict = dict(row._mapping)
                    symbol_path = row_dict.get("symbol_path")
                    if symbol_path:
                        if "uuid" in row_dict and row_dict["uuid"] is not None:
                            row_dict["uuid"] = str(row_dict["uuid"])
                        if (
                            "vector_id" in row_dict
                            and row_dict["vector_id"] is not None
                        ):
                            row_dict["vector_id"] = str(row_dict["vector_id"])
                        symbols_map[symbol_path] = row_dict
            else:
                async with get_session() as session:
                    result = await session.execute(
                        text("SELECT * FROM core.knowledge_graph ORDER BY symbol_path")
                    )
                    for row in result:
                        row_dict = dict(row._mapping)
                        symbol_path = row_dict.get("symbol_path")
                        if symbol_path:
                            if "uuid" in row_dict and row_dict["uuid"] is not None:
                                row_dict["uuid"] = str(row_dict["uuid"])
                            if (
                                "vector_id" in row_dict
                                and row_dict["vector_id"] is not None
                            ):
                                row_dict["vector_id"] = str(row_dict["vector_id"])
                            symbols_map[symbol_path] = row_dict
            knowledge_graph = {"symbols": symbols_map}
            logger.info(
                f"Successfully loaded {len(symbols_map)} symbols from the database."
            )
            return knowledge_graph
        except Exception as e:
            logger.error(
                f"Failed to load knowledge graph from database: {e}", exc_info=True
            )
            return {"symbols": {}}

    # ID: 1417d360-951e-41cf-a7f0-c4c3851bf30a
    async def list_capabilities(self) -> list[str]:
        """Returns all capability keys directly from the database."""
        if self._session:
            result = await self._session.execute(
                text("SELECT name FROM core.capabilities ORDER BY name")
            )
            return [row[0] for row in result]
        else:
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT name FROM core.capabilities ORDER BY name")
                )
                return [row[0] for row in result]

    # ID: 1c987828-05a4-4101-950c-1a6b56a2580f
    async def search_capabilities(self, query: str, limit: int = 5) -> list[str]:
        """
        This is a placeholder. Real semantic search happens in CognitiveService.
        """
        all_caps = await self.list_capabilities()
        q_lower = query.lower()
        return [c for c in all_caps if q_lower in c.lower()][:limit]
