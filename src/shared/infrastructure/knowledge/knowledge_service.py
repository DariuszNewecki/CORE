# src/shared/infrastructure/knowledge/knowledge_service.py

"""
Centralized access to CORE's knowledge graph and declared capabilities.

CONSTITUTIONAL COMPLIANCE:
- Treated as the read-only interface to the system state.
- Sourced from the operational database view `core.knowledge_graph`.

HEALED (V2.3.0):
- Shadow Sensation: Now accepts an optional LimbWorkspace.
- If a workspace is provided, it builds a "Shadow Graph" that includes
  uncommitted changes, preventing "Semantic Blindness" during refactoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)


# ID: bfdee087-408b-4c07-ab43-d673dbb3eca0
class KnowledgeService:
    """
    A read-only interface to the knowledge graph.
    """

    def __init__(
        self,
        repo_path: Path | str = ".",
        session=None,
        workspace: LimbWorkspace | None = None,
    ):
        self.repo_path = Path(repo_path)
        self._session = session
        self.workspace = workspace

    # ID: f508b9a0-3ddd-4e36-9c72-f5a19820b769
    async def get_graph(self) -> dict[str, Any]:
        """
        Loads the knowledge graph.

        HEALED: If a workspace is present, it returns a 'Shadow Graph' representing
        the future state of the code. Otherwise, it queries the database SSOT.
        """
        # SENSATION: Check the virtual overlay first
        if self.workspace:
            logger.info("📡 Sensation: Building Shadow Graph from workspace overlay...")
            from features.introspection.knowledge_graph_service import (
                KnowledgeGraphBuilder,
            )

            builder = KnowledgeGraphBuilder(self.repo_path, workspace=self.workspace)
            return builder.build()

        logger.info("Loading knowledge graph from database view...")
        symbols_map = {}
        try:

            async def _fetch_data(s):
                result = await s.execute(
                    text("SELECT * FROM core.knowledge_graph ORDER BY symbol_path")
                )
                return result.mappings().all()

            if self._session:
                rows = await _fetch_data(self._session)
            else:
                async with get_session() as session:
                    rows = await _fetch_data(session)

            for row in rows:
                row_dict = dict(row)
                symbol_path = row_dict.get("symbol_path")
                if symbol_path:
                    if "uuid" in row_dict and row_dict["uuid"] is not None:
                        row_dict["uuid"] = str(row_dict["uuid"])
                    if "vector_id" in row_dict and row_dict["vector_id"] is not None:
                        row_dict["vector_id"] = str(row_dict["vector_id"])
                    row_dict["capabilities"] = row_dict.get("capabilities_array", [])
                    symbols_map[symbol_path] = row_dict

            knowledge_graph = {"symbols": symbols_map}
            logger.info(
                "Successfully loaded %s symbols from the database.", len(symbols_map)
            )
            return knowledge_graph
        except Exception as e:
            logger.error(
                "Failed to load knowledge graph from database: %s", e, exc_info=True
            )
            return {"symbols": {}}

    # ID: f833244f-7d17-4510-be4b-9dcbd106e9fa
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

    # ID: 3f6515de-ffb2-4119-90c0-aecc89aae54a
    async def search_capabilities(self, query: str, limit: int = 5) -> list[str]:
        """
        Placeholder for semantic search (usually handled by CognitiveService).
        """
        all_caps = await self.list_capabilities()
        q_lower = query.lower()
        return [c for c in all_caps if q_lower in c.lower()][:limit]
