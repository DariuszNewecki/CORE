# src/features/introspection/drift_service.py
# ID: 58d789bd-6dc5-440d-ad53-efb8a204b43e

"""
Drift Service - Detects divergence between the Mind (Intent) and Body (Code).

CONSTITUTIONAL FIX (V2.3):
- Uses IntentRepository as the SSOT for declared capabilities.
- Removed dependency on legacy 'from_manifest.py' crawler.
"""

from __future__ import annotations

from pathlib import Path

from features.introspection.drift_detector import detect_capability_drift
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.models import CapabilityMeta, DriftReport


# ID: 58d789bd-6dc5-440d-ad53-efb8a204b43e
async def run_drift_analysis_async(root: Path) -> DriftReport:
    """
    Performs drift analysis by comparing manifest rules (Mind)
    against implemented symbols (Body).
    """
    # 1. Get Declared Capabilities from the Mind (IntentRepository)
    repo = get_intent_repository()
    # PathResolver handles mapping 'project_manifest' to the actual file
    manifest_data = repo.load_policy("project_manifest")
    declared_keys = manifest_data.get("capabilities", [])

    manifest_caps = {
        k: CapabilityMeta(key=k) for k in declared_keys if isinstance(k, str)
    }

    # 2. Get Implemented Capabilities from the Body (KnowledgeService)
    knowledge_service = KnowledgeService(root)
    graph = await knowledge_service.get_graph()

    code_caps: dict[str, CapabilityMeta] = {}
    for data in graph.get("symbols", {}).values():
        key = data.get("key")
        if key and key != "unassigned":
            code_caps[key] = CapabilityMeta(key=key, domain=data.get("domain"))

    return detect_capability_drift(manifest_caps, code_caps)
