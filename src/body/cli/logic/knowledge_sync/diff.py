# src/body/cli/logic/knowledge_sync/diff.py

"""
Compares database state with exported YAML files to detect drift in the CORE Working Mind.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from shared.config import settings
from shared.logger import getLogger

from .snapshot import fetch_capabilities, fetch_links, fetch_northstar, fetch_symbols
from .utils import _get_diff_links_key, canonicalize, read_yaml


logger = getLogger(__name__)
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


# ID: c91f9548-ee7e-4f43-8b86-29ce8e76c2ff
def diff_sets(
    db_items: list[dict[str, Any]], file_items: list[dict[str, Any]], key: str
) -> dict[str, Any]:
    """Compares two lists of dictionaries based on a key and returns the differences.

    Args:
        db_items: List of items from the database.
        file_items: List of items from the YAML file.
        key: The key to compare items by.

    Returns:
        Dictionary with 'only_db', 'only_file', and 'changed' lists.
    """
    db_map = {str(it.get(key)): it for it in db_items if it.get(key)}
    file_map = {str(it.get(key)): it for it in file_items if it.get(key)}
    only_db = sorted([k for k in db_map if k not in file_map])
    only_file = sorted([k for k in file_map if k not in db_map])
    changed = []
    for k in sorted(db_map.keys() & file_map.keys()):
        db_item = {
            kk: vv
            for kk, vv in db_map[k].items()
            if kk not in ("created_at", "updated_at", "first_seen", "last_seen")
        }
        file_item = {
            kk: vv
            for kk, vv in file_map[k].items()
            if kk not in ("created_at", "updated_at", "first_seen", "last_seen")
        }
        if canonicalize(db_item) != canonicalize(file_item):
            changed.append(k)
    return {"only_db": only_db, "only_file": only_file, "changed": changed}


# ID: 4a0003c6-29c2-44d7-8515-aad1adfc702a
async def run_diff(as_json: bool) -> dict[str, Any] | None:
    """Compares database state with exported YAML files and returns differences.

    Args:
        as_json: If True, returns the diff as JSON string; otherwise returns dict.

    Returns:
        Dictionary with diff results, JSON string if as_json=True, or None if export dir not found.
    """
    if not EXPORT_DIR.exists():
        logger.error(
            "Export directory not found: %s. Please run 'snapshot' first.", EXPORT_DIR
        )
        return None
    logger.info("Comparing database state with exported YAML files...")
    db_caps, db_syms, db_links, db_north = await asyncio.gather(
        fetch_capabilities(), fetch_symbols(), fetch_links(), fetch_northstar()
    )
    file_caps = read_yaml(EXPORT_DIR / "capabilities.yaml").get("items", [])
    file_syms = read_yaml(EXPORT_DIR / "symbols.yaml").get("items", [])
    file_links = read_yaml(EXPORT_DIR / "links.yaml").get("items", [])
    file_north = read_yaml(EXPORT_DIR / "northstar.yaml").get("items", [])
    output = {
        "capabilities": diff_sets(db_caps, file_caps, "id"),
        "symbols": diff_sets(db_syms, file_syms, "id"),
        "links": diff_sets(
            [dict(it, key=_get_diff_links_key(it)) for it in db_links],
            [dict(it, key=_get_diff_links_key(it)) for it in file_links],
            "key",
        ),
        "northstar": {"changed": canonicalize(db_north) != canonicalize(file_north)},
    }
    if as_json:
        return json.dumps(output, indent=2)
    return output
