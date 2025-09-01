# src/system/guard/models.py
"""
Intent: Provides the shared data models for the governance guard tools,
breaking a potential circular import dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
# CAPABILITY: system.capability.metadata
class CapabilityMeta:
    """A minimal, shared data container for capability metadata."""

    capability: str
    domain: Optional[str] = None
    owner: Optional[str] = None


@dataclass
# CAPABILITY: system.guard.report_drift
class DriftReport:
    """Structured result for capability drift suitable for JSON emission and CI gating."""

    missing_in_code: List[str]
    undeclared_in_manifest: List[str]
    mismatched_mappings: List[Dict[str, Dict[str, Optional[str]]]]

    # CAPABILITY: system.guard.serialize_drift_report
    def to_dict(self) -> dict:
        """Converts the drift report into a stable JSON-serializable dict."""
        return {
            "missing_in_code": sorted(self.missing_in_code),
            "undeclared_in_manifest": sorted(self.undeclared_in_manifest),
            "mismatched_mappings": self.mismatched_mappings,
        }
