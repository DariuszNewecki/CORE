# src/system/guard/discovery/from_kgb.py
"""
Intent: Provides a focused tool for discovering capabilities by running the
live KnowledgeGraphBuilder.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Optional

from system.guard.models import CapabilityMeta


def _try_import_kgb():
    """Attempts to access KnowledgeGraphBuilder without a static cross-domain import."""
    try:
        mod = importlib.import_module("system.tools.codegraph_builder")
        return getattr(mod, "KnowledgeGraphBuilder", None)
    except Exception:
        return None


def _extract_cap_meta_from_node(node: Dict[str, Any]) -> Optional[CapabilityMeta]:
    """Extracts capability metadata from a Knowledge Graph node."""
    cap = node.get("capability")
    if cap and cap != "unassigned":
        return CapabilityMeta(
            capability=str(cap),
            domain=str(node.get("domain")) if node.get("domain") else None,
            owner=str(node.get("agent")) if node.get("agent") else None,
        )
    return None


def collect_from_kgb(root: Path) -> Dict[str, CapabilityMeta]:
    """Uses KnowledgeGraphBuilder (if present) to discover capabilities from the repo."""
    KGB = _try_import_kgb()
    if not KGB:
        return {}
    try:
        builder = KGB(root_path=root)
        graph = builder.build()
        caps: Dict[str, CapabilityMeta] = {}
        if isinstance(graph, dict):
            symbols = graph.get("symbols", {})
            for node in symbols.values():
                if isinstance(node, dict):
                    meta = _extract_cap_meta_from_node(node)
                    if meta:
                        caps[meta.capability] = meta
        return caps
    except Exception:
        return {}
