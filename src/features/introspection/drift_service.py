# src/features/introspection/drift_service.py
"""
Provides a dedicated service for detecting drift between the declared constitution
and the implemented reality of the codebase.
"""

from __future__ import annotations

from pathlib import Path

from features.introspection.discovery.from_manifest import (
    load_manifest_capabilities,
)
from features.introspection.drift_detector import detect_capability_drift
from services.knowledge.knowledge_service import KnowledgeService
from shared.models import CapabilityMeta, DriftReport


# ID: 58d789bd-6dc5-440d-ad53-efb8a204b4d3
async def run_drift_analysis_async(root: Path) -> DriftReport:
    """
    Performs a full drift analysis by comparing manifest capabilities
    against the capabilities discovered in the codebase via the KnowledgeService.
    """
    manifest_caps = load_manifest_capabilities(root, explicit_path=None)

    knowledge_service = KnowledgeService(root)
    graph = await knowledge_service.get_graph()

    code_caps: dict[str, CapabilityMeta] = {}
    for symbol in graph.get("symbols", {}).values():
        key = symbol.get("key")
        if key and key != "unassigned":
            code_caps[key] = CapabilityMeta(
                key=key,
                domain=symbol.get("domain"),
                owner=symbol.get("owner"),
            )

    return detect_capability_drift(manifest_caps, code_caps)
