# src/shared/utils/manifest_aggregator.py
"""
Aggregates domain-specific manifests into a unified system constitution.
"""

from __future__ import annotations

# src/shared/utils/manifest_aggregator.py
"""
A utility to discover and aggregate domain-specific manifests into a single,
unified view of the system's constitution.
"""
from pathlib import Path
from typing import Any, Dict

import yaml

from shared.logger import getLogger

log = getLogger("manifest_aggregator")


def aggregate_manifests(repo_root: Path) -> Dict[str, Any]:
    """
    Finds all domain-specific manifest.yaml files and merges them.

    This function is the heart of the modular manifest system. It reads the
    source structure to find all domains, then searches for a manifest in each
    domain's directory, aggregating their contents.

    Args:
        repo_root (Path): The absolute path to the repository root.

    Returns:
        A dictionary representing the aggregated manifest, primarily focused
        on compiling a unified list of 'required_capabilities'.
    """
    log.info("🔍 Starting manifest aggregation...")
    source_structure_path = (
        repo_root / ".intent" / "knowledge" / "source_structure.yaml"
    )
    if not source_structure_path.exists():
        log.error("❌ Cannot aggregate manifests: source_structure.yaml not found.")
        return {}

    source_structure = yaml.safe_load(source_structure_path.read_text())

    all_capabilities = []
    domains_found = 0

    for domain_entry in source_structure.get("structure", []):
        domain_path_str = domain_entry.get("path")
        if not domain_path_str:
            continue

        manifest_path = repo_root / domain_path_str / "manifest.yaml"
        if manifest_path.exists():
            domains_found += 1
            log.debug(
                f"   -> Found manifest for domain '{domain_entry.get('domain')}' at {manifest_path}"
            )
            domain_manifest = yaml.safe_load(manifest_path.read_text())
            if domain_manifest and "capabilities" in domain_manifest:
                all_capabilities.extend(domain_manifest["capabilities"])

    log.info(f"   -> Aggregated capabilities from {domains_found} domain manifests.")

    # We also keep some top-level info from the original monolithic manifest for now
    # to ensure a smooth transition.
    monolith_path = repo_root / ".intent" / "project_manifest.yaml"
    monolith_data = {}
    if monolith_path.exists():
        monolith_data = yaml.safe_load(monolith_path.read_text())

    aggregated_manifest = {
        "name": monolith_data.get("name", "CORE"),
        "intent": monolith_data.get("intent", "No intent provided."),
        "active_agents": monolith_data.get("active_agents", []),
        "required_capabilities": sorted(list(set(all_capabilities))),
    }

    return aggregated_manifest
