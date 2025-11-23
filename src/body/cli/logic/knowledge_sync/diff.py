# src/body/cli/logic/knowledge_sync/diff.py
"""
Compares database state with exported YAML files to detect drift in the CORE Working Mind.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.console import Console

from shared.config import settings

from .snapshot import fetch_capabilities, fetch_links, fetch_northstar, fetch_symbols
from .utils import _get_diff_links_key, canonicalize, read_yaml

console = Console()
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


# ID: e066d956-a155-42b5-be8c-adb693371b99
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


# ID: b12e8b4a-a760-436a-9529-3919081a1a43
async def run_diff(as_json: bool) -> None:
    """Compares database state with exported YAML files and outputs differences.

    Args:
        as_json: If True, outputs the diff as JSON; otherwise, uses human-readable format.
    """
    if not EXPORT_DIR.exists():
        console.print(
            f"[bold red]Export directory not found: {EXPORT_DIR}. "
            "Please run 'snapshot' first.[/bold red]"
        )
        return

    console.print("🔄 Comparing database state with exported YAML files...")

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
        console.print(json.dumps(output, indent=2))
    else:
        console.print("\n[bold]Diff Summary (Database <-> Files):[/bold]")
        for k, v in output.items():
            if k == "northstar":
                status = (
                    "[red]Changed[/red]" if v["changed"] else "[green]No change[/green]"
                )
                console.print(f"  - [cyan]{k.capitalize()}[/cyan]: {status}")
                continue

            counts = (
                f"DB-only: {len(v['only_db'])}, "
                f"File-only: {len(v['only_file'])}, "
                f"Changed: {len(v['changed'])}"
            )
            is_clean = not any(v.values())
            status = (
                "[green]Clean[/green]"
                if is_clean
                else "[yellow]Drift detected[/yellow]"
            )
            console.print(f"  - [cyan]{k.capitalize()}[/cyan]: {status} ({counts})")
