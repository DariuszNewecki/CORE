# src/system/guard/discovery/from_manifest.py
"""
Intent: Provides a focused tool for discovering capabilities from manifest files.
This version is updated to support the modular manifest architecture.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

from system.guard.models import CapabilityMeta


def _normalize_cap_list(items: Any) -> Dict[str, CapabilityMeta]:
    """Normalizes various list/dict shapes into a standard {cap: Meta} dictionary."""
    out: Dict[str, CapabilityMeta] = {}
    if isinstance(items, list):
        for it in items:
            if isinstance(it, str):
                out[it] = CapabilityMeta(it)
    return out


def _find_all_manifests(start: Path) -> list[Path]:
    """Locates all manifest.yaml files within the src directory."""
    src_path = start / "src"
    if not src_path.is_dir():
        return []
    return sorted(list(src_path.glob("**/manifest.yaml")))


def load_manifest_capabilities(
    root: Path, explicit_path: Optional[Path] = None
) -> Dict[str, CapabilityMeta]:
    """
    Loads, parses, and aggregates capabilities from all domain-specific manifests.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required to load manifests.")

    all_caps: Dict[str, CapabilityMeta] = {}
    manifest_paths = _find_all_manifests(root)

    for path in manifest_paths:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # Extract capabilities and associate them with their domain
            domain = data.get("domain", "unknown")
            caps_list = data.get("capabilities", [])
            normalized_caps = _normalize_cap_list(caps_list)

            for cap, meta in normalized_caps.items():
                if cap not in all_caps:
                    all_caps[cap] = CapabilityMeta(capability=cap, domain=domain)
        except Exception:
            # Ignore files that fail to parse
            continue

    return all_caps
