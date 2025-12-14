# src/shared/utils/manifest_aggregator.py

"""
Aggregates domain-specific capability definitions from the constitution into a unified view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e3291d01-7675-4c22-9454-05a31107893d
def aggregate_manifests(repo_root: Path) -> dict[str, Any]:
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
    logger.debug(
        "🔍 Starting manifest aggregation by searching all constitutional sources..."
    )
    all_capabilities = []
    manifests_found = 0
    proposed_manifests_dir = repo_root / "reports" / "proposed_manifests"
    live_manifests_dir = repo_root / ".intent" / "knowledge" / "domains"
    if proposed_manifests_dir.is_dir() and any(proposed_manifests_dir.iterdir()):
        search_dir = proposed_manifests_dir
        logger.warning(
            "   -> ⚠️ Found proposed manifests. Auditor will use these for validation."
        )
    else:
        search_dir = live_manifests_dir
    if search_dir.is_dir():
        for domain_file in sorted(search_dir.glob("*.yaml")):
            manifests_found += 1
            logger.debug("   -> Loading capabilities from: %s", domain_file.name)
            try:
                domain_manifest = yaml.safe_load(domain_file.read_text()) or {}
                if "tags" in domain_manifest and isinstance(
                    domain_manifest["tags"], list
                ):
                    all_capabilities.extend(domain_manifest["tags"])
            except yaml.YAMLError as e:
                logger.error(
                    "   -> ❌ Skipping invalid YAML file: %s - %s", domain_file.name, e
                )
                continue
    logger.debug(
        "   -> Aggregated capabilities from %s domain manifests.", manifests_found
    )
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
