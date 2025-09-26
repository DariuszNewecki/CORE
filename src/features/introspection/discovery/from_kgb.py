# src/features/introspection/discovery/from_kgb.py
"""
Discovers implemented capabilities by leveraging the KnowledgeGraphBuilder.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.models import CapabilityMeta


# ID: 12a7fddd-fa62-4dd8-8e1b-54208392a078
def collect_from_kgb(root: Path) -> Dict[str, CapabilityMeta]:
    """
    Uses the KnowledgeGraphBuilder to find all capabilities.
    """
    builder = KnowledgeGraphBuilder(root_path=root)
    graph = builder.build()

    capabilities: Dict[str, CapabilityMeta] = {}
    for symbol in graph.get("symbols", {}).values():
        cap_key = symbol.get("capability")
        if cap_key and cap_key != "unassigned":
            capabilities[cap_key] = CapabilityMeta(
                key=cap_key,
                domain=symbol.get("domain"),
                owner=symbol.get("owner"),
            )
    return capabilities
