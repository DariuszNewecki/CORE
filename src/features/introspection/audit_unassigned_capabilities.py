# src/features/introspection/audit_unassigned_capabilities.py

"""
Provides a utility to find and report on symbols in the knowledge graph
that have not been assigned a capability ID.
"""

from __future__ import annotations

import asyncio
from typing import Any

from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 45fb19cb-d3a3-49cb-82c8-6665248df90b
def get_unassigned_symbols() -> list[dict[str, Any]]:
    """
    Scans the knowledge graph for governable symbols with a capability of
    'unassigned' and returns them.
    """

    async def _async_get():
        knowledge_service = KnowledgeService(settings.REPO_PATH)
        graph = await knowledge_service.get_graph()
        symbols = graph.get("symbols", {})
        unassigned = []
        for key, symbol_data in symbols.items():
            name = symbol_data.get("name")
            if name is None:
                continue
            is_public = not name.startswith("_")
            is_unassigned = symbol_data.get("capability") == "unassigned"
            if is_public and is_unassigned:
                symbol_data["key"] = key
                unassigned.append(symbol_data)
        return unassigned

    try:
        return asyncio.run(_async_get())
    except Exception as e:
        logger.error("Error processing knowledge graph: %s", e)
        return []
