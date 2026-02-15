# src/features/introspection/discovery/from_kgb.py
"""
Discovers implemented capabilities by leveraging the KnowledgeGraphBuilder.
"""

from __future__ import annotations

from pathlib import Path

from body.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.models import CapabilityMeta


def _collect_from_kgb(root: Path) -> dict[str, CapabilityMeta]:
    """
    Internal helper: use the KnowledgeGraphBuilder to find all capabilities.

    This is a strategy used by the higher-level capability discovery service.
    It is not a public capability surface on its own.
    """
    builder = KnowledgeGraphBuilder(root_path=root)
    graph = builder.build()

    capabilities: dict[str, CapabilityMeta] = {}
    for symbol in graph.get("symbols", {}).values():
        cap_key = symbol.get("capability")
        if cap_key and cap_key != "unassigned":
            capabilities[cap_key] = CapabilityMeta(
                key=cap_key,
                domain=symbol.get("domain"),
                owner=symbol.get("owner"),
            )
    return capabilities
