# src/system/guard/capability_discovery.py
"""
Intent: Orchestrates the discovery of capabilities from all available sources,
respecting the principle of precedence (live analysis > source scan).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .discovery import from_kgb, from_manifest, from_source_scan
from .models import CapabilityMeta


# CAPABILITY: system.capability.discover
def collect_code_capabilities(
    root: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
    require_kgb: bool = False,
) -> Dict[str, CapabilityMeta]:
    """
    Unified discovery entrypoint that tries the live KnowledgeGraphBuilder first,
    then falls back to a direct source scan.
    """
    caps = from_kgb.collect_from_kgb(root)
    if caps:
        return caps

    if require_kgb:
        raise RuntimeError(
            "Strict intent mode: No capabilities found from KnowledgeGraphBuilder."
        )

    include = include_globs or []
    exclude = exclude_globs or ["**/.git/**", "**/.venv/**", "**/__pycache__/**"]
    return from_source_scan.collect_from_source_scan(root, include, exclude)


# CAPABILITY: system.manifest.load_capabilities
def load_manifest_capabilities(
    root: Path, explicit_path: Optional[Path] = None
) -> Dict[str, CapabilityMeta]:
    """Loads, parses, and normalizes capabilities from the project's manifest."""
    return from_manifest.load_manifest_capabilities(root, explicit_path)
