# src/system/guard/capability_discovery.py
"""
Intent: Orchestrates the discovery of capabilities from all available sources,
respecting the principle of precedence (live analysis > source scan).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

# --- START OF FIX ---
# This import line now correctly includes all three required discovery modules.
from system.guard.discovery import from_kgb, from_manifest, from_source_scan

# --- END OF FIX ---
from system.guard.models import CapabilityMeta
from system.tools.domain_mapper import DomainMapper


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
    # Primary Method: Use the Knowledge Graph Builder
    caps = from_kgb.collect_from_kgb(root)
    if caps:
        return caps

    if require_kgb:
        raise RuntimeError(
            "Strict intent mode: No capabilities found from KnowledgeGraphBuilder."
        )

    # Fallback Method: If KGB finds nothing, scan the source directly.
    # This now correctly passes the DomainMapper to make the fallback constitution-aware.
    domain_mapper = DomainMapper(root)
    include = include_globs or []
    exclude = exclude_globs or ["**/.git/**", "**/.venv/**", "**/__pycache__/**"]
    return from_source_scan.collect_from_source_scan(
        root, include, exclude, domain_mapper=domain_mapper
    )


def load_manifest_capabilities(
    root: Path, explicit_path: Optional[Path] = None
) -> Dict[str, CapabilityMeta]:
    """Loads, parses, and normalizes capabilities from the project's manifest."""
    # This function is essential and is now correctly included.
    return from_manifest.load_manifest_capabilities(root, explicit_path)
