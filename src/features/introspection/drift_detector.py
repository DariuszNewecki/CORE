# src/features/introspection/drift_detector.py
"""
Detects drift between declared capabilities in manifests and implemented
capabilities in the source code.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from shared.models import CapabilityMeta, DriftReport


# ID: 6cc5efdf-037e-4862-b13e-0a569d889a97
def detect_capability_drift(
    manifest_caps: dict[str, CapabilityMeta], code_caps: dict[str, CapabilityMeta]
) -> DriftReport:
    """
    Compares two dictionaries of capabilities and returns a drift report.
    """
    manifest_keys: set[str] = set(manifest_caps.keys())
    code_keys: set[str] = set(code_caps.keys())

    missing_in_code = sorted(list(manifest_keys - code_keys))
    undeclared_in_manifest = sorted(list(code_keys - manifest_keys))

    mismatched = []
    for key in manifest_keys.intersection(code_keys):
        manifest_cap = manifest_caps[key]
        code_cap = code_caps[key]
        if manifest_cap != code_cap:
            mismatched.append(
                {
                    "capability": key,
                    "manifest": asdict(manifest_cap),
                    "code": asdict(code_cap),
                }
            )

    return DriftReport(
        missing_in_code=missing_in_code,
        undeclared_in_manifest=undeclared_in_manifest,
        mismatched_mappings=mismatched,
    )


# ID: db10bc9b-b4b3-41f2-8d81-b32731540d95
def write_report(path: Path, report: DriftReport) -> None:
    """Writes the drift report to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
