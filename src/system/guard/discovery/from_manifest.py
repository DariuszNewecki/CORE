# src/system/guard/discovery/from_manifest.py
"""
Intent: Provides a focused tool for discovering capabilities from manifest files.
This version understands the new modular manifest architecture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import yaml

from system.guard.models import CapabilityMeta


def load_manifest_capabilities(
    root: Path, explicit_path: Optional[Path] = None
) -> Dict[str, CapabilityMeta]:
    """
    Loads, parses, and normalizes capabilities by aggregating all domain-specific manifests.
    """
    if explicit_path:
        # If an explicit path is given, we load just that one for simplicity.
        # This path is not used in our current tests but is kept for utility.
        with explicit_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            caps = data.get("capabilities", [])
            return {cap: CapabilityMeta(capability=cap) for cap in caps}

    # This is the primary logic path: discover and aggregate all manifests.
    source_structure_path = root / ".intent/knowledge/source_structure.yaml"
    if not source_structure_path.exists():
        raise FileNotFoundError(
            "Cannot load manifest capabilities: source_structure.yaml not found."
        )

    structure = yaml.safe_load(source_structure_path.read_text()) or {}
    all_capabilities: set[str] = set()

    for domain_entry in structure.get("structure", []):
        domain_path_str = domain_entry.get("path")
        if not domain_path_str:
            continue

        manifest_path = root / domain_path_str / "manifest.yaml"
        if manifest_path.exists():
            domain_manifest = yaml.safe_load(manifest_path.read_text()) or {}
            if "capabilities" in domain_manifest:
                all_capabilities.update(domain_manifest["capabilities"])

    return {
        cap: CapabilityMeta(capability=cap) for cap in sorted(list(all_capabilities))
    }
