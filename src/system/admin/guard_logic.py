# src/system/admin/guard_logic.py

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from system.guard.capability_discovery import (
    collect_code_capabilities,
    load_manifest_capabilities,
)
from system.guard.drift_detector import detect_capability_drift


def run_drift(root: Path, strict_intent: bool = False) -> Dict[str, Any]:
    """
    Pure function: computes capability drift and returns a report dictionary.
    This function MUST NOT print, write files, or exit.
    """
    # 1. Discover capabilities from the code using the appropriate discovery tools.
    code_caps = collect_code_capabilities(root, require_kgb=strict_intent)

    # 2. Load the declared capabilities from all domain manifests.
    manifest_caps = load_manifest_capabilities(root)

    # 3. Compare the two sets to find any drift.
    report = detect_capability_drift(manifest_caps, code_caps)

    # 4. Return the result as a JSON-serializable dictionary.
    return report.to_dict()
