# src/features/introspection/audit_unassigned_capabilities.py
"""
Provides a utility to find and report on symbols in the knowledge graph
that have not been assigned a capability ID.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from core.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger

log = getLogger("audit_unassigned_caps")


# ID: d93e7a47-27c1-4fa5-bf39-0a44bef8bf59
def get_unassigned_symbols() -> List[Dict[str, Any]]:
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
            is_public = not symbol_data.get("name", "").startswith("_")
            is_unassigned = symbol_data.get("capability") == "unassigned"

            if is_public and is_unassigned:
                symbol_data["key"] = key
                unassigned.append(symbol_data)
        return unassigned

    try:
        return asyncio.run(_async_get())
    except Exception as e:
        log.error(f"Error processing knowledge graph: {e}")
        return []
