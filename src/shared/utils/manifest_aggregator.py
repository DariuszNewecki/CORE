# src/shared/utils/manifest_aggregator.py

"""
Aggregates domain-specific capability definitions from the constitution into a unified view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from shared.logger import getLogger

log = getLogger("manifest_aggregator")


# ID: 5f0549df-0ce5-468a-a232-c61663724a77
def aggregate_manifests(repo_root: Path) -> Dict[str, Any]:
    """
    Finds all domain-specific capability definition YAML files and merges them.
    This is "canary-aware": if a 'reports/proposed_manifests' directory
    exists, it will be used as the source of truth instead of the live
    '.intent/knowledge/domains' manifests.

    Args:
        repo_root (Path): The absolute path to the repository root.

    Returns:
        A dictionary representing the aggregated manifest.
    """
    # --- THIS IS THE FIX: Changed from log.info to log.debug ---
    log.debug(
        "🔍 Starting manifest aggregation by searching all constitutional sources..."
    )
    all_capabilities = []
    manifests_found = 0

    proposed_manifests_dir = repo_root / "reports" / "proposed_manifests"
    live_manifests_dir = repo_root / ".intent" / "knowledge" / "domains"

    if proposed_manifests_dir.is_dir() and any(proposed_manifests_dir.iterdir()):
        search_dir = proposed_manifests_dir
        log.warning(
            "   -> ⚠️ Found proposed manifests. Auditor will use these for validation."
        )
    else:
        search_dir = live_manifests_dir

    if search_dir.is_dir():
        for domain_file in sorted(search_dir.glob("*.yaml")):
            manifests_found += 1
            log.debug(f"   -> Loading capabilities from: {domain_file.name}")
            try:
                domain_manifest = yaml.safe_load(domain_file.read_text()) or {}
                if "tags" in domain_manifest and isinstance(
                    domain_manifest["tags"], list
                ):
                    all_capabilities.extend(domain_manifest["tags"])
            except yaml.YAMLError as e:
                log.error(
                    f"   -> ❌ Skipping invalid YAML file: {domain_file.name} - {e}"
                )
                continue

    log.debug(f"   -> Aggregated capabilities from {manifests_found} domain manifests.")

    monolith_path = repo_root / ".intent" / "project_manifest.yaml"
    monolith_data = {}
    if monolith_path.exists():
        monolith_data = yaml.safe_load(monolith_path.read_text())

    unique_caps = set()
    for item in all_capabilities:
        if isinstance(item, str):
            unique_caps.add(item)
        elif isinstance(item, dict) and "key" in item:
            unique_caps.add(item["key"])

    unique_caps.update(monolith_data.get("required_capabilities", []))

    return {
        "name": monolith_data.get("name", "CORE"),
        "intent": monolith_data.get("intent", "No intent provided."),
        "active_agents": monolith_data.get("active_agents", []),
        "required_capabilities": sorted(list(unique_caps)),
    }
