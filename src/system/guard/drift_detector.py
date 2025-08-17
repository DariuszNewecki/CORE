# src/system/guard/drift_detector.py
"""
Intent: Compares two sets of capabilities (from manifest and code) to detect
drift and produces a machine-readable report.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import CapabilityMeta, DriftReport


def detect_capability_drift(
    manifest_caps: Dict[str, CapabilityMeta], code_caps: Dict[str, CapabilityMeta]
) -> DriftReport:
    """Computes missing, undeclared, and mismatched capabilities between manifest and code."""
    m_keys = set(manifest_caps.keys())
    c_keys = set(code_caps.keys())

    missing = sorted(list(m_keys - c_keys))
    undeclared = sorted(list(c_keys - m_keys))

    mismatches: List[Dict[str, Dict[str, Optional[str]]]] = []
    for k in sorted(list(m_keys & c_keys)):
        m = manifest_caps[k]
        c = code_caps[k]
        # --- THIS IS THE FIX ---
        # We will only compare the 'domain' for now, as 'owner' is not
        # a field that is declared in the manifest files.
        if m.domain != c.domain:
            # --- END OF FIX ---
            mismatches.append(
                {
                    "capability": k,
                    "manifest": {"domain": m.domain, "owner": m.owner},
                    "code": {"domain": c.domain, "owner": c.owner},
                }
            )

    return DriftReport(missing, undeclared, mismatches)


def write_report(report_path: Path, report: DriftReport) -> None:
    """Persists the drift report to disk for evidence and CI."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
