# src/body/introspection/drift_service.py
"""
Symbols-drift service stub — ADR-143 D1.

Detection of missing # ID: anchors is owned by the purity.stable_id_anchor
audit rule + fix.ids remediation action. Querying the blackboard for open
purity.stable_id_anchor findings IS the governed answer — no parallel scanner.

Pending ADR-143 D3: wire this endpoint to query existing blackboard findings
rather than re-scanning.
"""

from __future__ import annotations

from pathlib import Path


# ID: 51f59218-c7f5-41ae-b2c9-87d4459e14d2
async def run_drift_analysis_async(root: Path) -> dict:
    """Symbols-drift stub — pending ADR-143 D3 implementation."""
    return {
        "available": False,
        "error": "symbols-drift not yet wired — see ADR-143 D3 (#503)",
    }
