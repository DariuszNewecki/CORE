# src/cli/logic/mind_ssot.py
"""
Phase 2, 3, & 4: Deterministic DB <-> YAML mirror for the Working Mind.
This file contains the core logic for the 'snapshot', 'diff', 'import', and 'verify' commands.
"""

from __future__ import annotations

import asyncio
import getpass
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml
from rich.console import Console
from services.database.models import Capability, Northstar, Symbol, SymbolCapabilityLink
from services.database.session_manager import get_session
from shared.config import settings
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

console = Console()
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


# --- Helper Functions from your plan ---


# ID: bca8d420-49c6-4f18-aa43-6b4dd7f0f850
def iso_now() -> str:
    """Returns the current UTC time in a standard format."""
    return datetime.now(timezone.utc).isoformat()


# ID: dec9deb3-1e13-4d2a-a0cd-dcae4b248ac1
def canonicalize(obj: Any) -> Any:
    """Recursively sorts dictionary keys to ensure a stable, consistent order for hashing."""
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        if all(isinstance(i, dict) for i in obj):
            try:
                return sorted(obj, key=lambda x: str(x.get("id", "")))
            except TypeError:
                pass
        return [canonicalize(x) for x in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


# ID: 5e482eda-feb8-46d8-b4fd-d4c80bb23372
def compute_digest(items: List[Dict[str, Any]]) -> str:
    """Creates a unique fingerprint (SHA256) for a list of items."""
    canon = canonicalize(items)
    payload = json.dumps(
        canon, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


# ID: 868c75af-85f7-4f90-9f3b-87806b2b4ee9
def write_yaml(path: Path, items: List[Dict[str, Any]], exported_at: str) -> str:
    """Writes a list of items to a YAML file, including version, timestamp, and the unique digest."""
    # Convert UUIDs to strings for YAML serialization
    stringified_items = [
        {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in item.items()}
        for item in items
    ]
    digest = compute_digest(stringified_items)
    doc = {
        "version": 1,
        "exported_at": exported_at,
        "items": stringified_items,
        "digest": digest,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, indent=2)
    return digest


# ID: 7ff299a6-9403-41c7-9522-e4f8d1ad90b1
def read_yaml(path: Path) -> Dict[str, Any]:
    """Reads a YAML file and returns its content, handling missing files."""
    if not path.exists():
        return {"items": [], "digest": None}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        # Convert string IDs back to UUID objects for database operations
        if "items" in data and isinstance(data["items"], list):
            for item in data["items"]:
                if "id" in item:
                    item["id"] = uuid.UUID(item["id"])
                if "symbol_id" in item:
                    item["symbol_id"] = uuid.UUID(item["symbol_id"])
                if "capability_id" in item:
                    item["capability_id"] = uuid.UUID(item["capability_id"])
        return data


# --- Database Fetcher Functions ---


# ID: aedf8f51-f30e-48aa-b5a7-fb82f2e090cd
async def fetch_capabilities() -> List[Dict[str, Any]]:
    """Reads all capabilities from the database, ordered consistently."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, name, objective, owner, domain, tags, status FROM core.capabilities ORDER BY lower(domain), lower(name), id"
            )
        )
        return [dict(row) for row in result.mappings()]


# ID: e1dce0f7-3ac3-430d-bc6c-c73d278a869b
async def fetch_symbols() -> List[Dict[str, Any]]:
    """Reads all symbols from the database, ordered consistently."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, module, qualname, kind, ast_signature, fingerprint, state FROM core.symbols ORDER BY fingerprint, id"
            )
        )
        return [dict(row) for row in result.mappings()]


# ID: 5cab9fd9-1ff7-448d-a11a-f511dbc614d8
async def fetch_links() -> List[Dict[str, Any]]:
    """Reads all symbol-capability links from the database, ordered consistently."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT symbol_id, capability_id, confidence, source, verified FROM core.symbol_capability_links ORDER BY capability_id, symbol_id, source"
            )
        )
        rows = [dict(row) for row in result.mappings()]
        for r in rows:
            if "confidence" in r and r["confidence"] is not None:
                r["confidence"] = float(r["confidence"])
        return rows


# ID: 3de03ab6-c94e-4834-a7ef-eb1809219d35
async def fetch_northstar() -> List[Dict[str, Any]]:
    """Reads the current North Star mission from the database."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, mission FROM core.northstar ORDER BY updated_at DESC LIMIT 1"
            )
        )
        return [dict(row) for row in result.mappings()]


# --- Main Snapshot Logic ---


# ID: e731e7aa-1169-4e24-a1cb-cdc1461d607f
async def run_snapshot(env: str | None, note: str | None):
    """The main function that performs the snapshot operation."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    exported_at = iso_now()
    who = getpass.getuser()
    env = env or "dev"

    console.print(f"📸 Creating a new snapshot of the database in '{EXPORT_DIR}'...")

    caps, syms, links, north = await asyncio.gather(
        fetch_capabilities(), fetch_symbols(), fetch_links(), fetch_northstar()
    )

    digests = []
    digests.append(
        (
            "capabilities.yaml",
            write_yaml(EXPORT_DIR / "capabilities.yaml", caps, exported_at),
        )
    )
    digests.append(
        ("symbols.yaml", write_yaml(EXPORT_DIR / "symbols.yaml", syms, exported_at))
    )
    digests.append(
        ("links.yaml", write_yaml(EXPORT_DIR / "links.yaml", links, exported_at))
    )
    digests.append(
        (
            "northstar.yaml",
            write_yaml(EXPORT_DIR / "northstar.yaml", north, exported_at),
        )
    )

    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "INSERT INTO core.export_manifests (who, environment, notes) VALUES (:who, :env, :note) RETURNING id"
                ),
                {"who": who, "env": env, "note": note},
            )
            manifest_id = result.scalar_one()

            for relpath, sha in digests:
                await session.execute(
                    text(
                        """
                        INSERT INTO core.export_digests (path, sha256, manifest_id)
                        VALUES (:path, :sha, :manifest_id)
                        ON CONFLICT (path) DO UPDATE SET
                          sha256 = EXCLUDED.sha256,
                          manifest_id = EXCLUDED.manifest_id,
                          exported_at = NOW()
                    """
                    ),
                    {
                        "path": str(
                            EXPORT_DIR.relative_to(settings.REPO_PATH) / relpath
                        ),
                        "sha": sha,
                        "manifest_id": manifest_id,
                    },
                )

    console.print("[bold green]✅ Snapshot complete.[/bold green]")
    for rel, sha in digests:
        console.print(f"  - Wrote '{rel}' with digest: {sha}")


# --- Main Diff Logic ---


# ID: 5c90462f-f36c-48c6-940b-25b8c1311ee3
def diff_sets(
    db_items: List[Dict[str, Any]], file_items: List[Dict[str, Any]], key: str
) -> Dict[str, Any]:
    """Compares two lists of dictionaries based on a key and returns the differences."""
    db_map = {str(it[key]): it for it in db_items}
    file_map = {str(it[key]): it for it in file_items}

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


def _get_diff_links_key(item: Dict[str, Any]) -> str:
    """Creates a stable composite key for a link dictionary."""
    return f"{str(item.get('symbol_id', ''))}-{str(item.get('capability_id', ''))}-{item.get('source', '')}"


# ID: ea814f0f-bee9-4c32-ae1c-fa9f474eabaf
async def run_diff(as_json: bool):
    """Orchestrates the diff operation."""
    if not EXPORT_DIR.exists():
        console.print(
            f"[bold red]Export directory not found: {EXPORT_DIR}. Please run 'snapshot' first.[/bold red]"
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

            counts = f"DB-only: {len(v['only_db'])}, File-only: {len(v['only_file'])}, Changed: {len(v['changed'])}"
            is_clean = not any(v.values())
            status = (
                "[green]Clean[/green]"
                if is_clean
                else "[yellow]Drift detected[/yellow]"
            )
            console.print(f"  - [cyan]{k.capitalize()}[/cyan]: {status} ({counts})")


# --- Main Import Logic ---


async def _upsert_items(session, table_model, items, index_elements):
    """Generic upsert function for our SSOT tables."""
    if not items:
        return
    stmt = pg_insert(table_model).values(items)
    update_dict = {
        c.name: getattr(stmt.excluded, c.name)
        for c in stmt.table.columns
        if not c.primary_key
    }
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_=update_dict,
    )
    await session.execute(upsert_stmt)


# ID: 2bf1f61e-bde5-4f19-ba76-07e5a8987fa2
async def run_import(dry_run: bool):
    """Orchestrates the import operation."""
    if not EXPORT_DIR.exists():
        console.print(
            f"[bold red]Export directory not found: {EXPORT_DIR}. Cannot import.[/bold red]"
        )
        return

    docs_to_check = {
        "capabilities": EXPORT_DIR / "capabilities.yaml",
        "symbols": EXPORT_DIR / "symbols.yaml",
        "links": EXPORT_DIR / "links.yaml",
        "northstar": EXPORT_DIR / "northstar.yaml",
    }

    docs = {name: read_yaml(path) for name, path in docs_to_check.items()}

    for name, doc in docs.items():
        if doc.get("digest") and doc.get("digest") != compute_digest(
            doc.get("items", [])
        ):
            console.print(
                f"[bold red]Digest mismatch in {name}.yaml! Aborting import. Run 'snapshot' to regenerate.[/bold red]"
            )
            return

    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: The following actions would be taken --[/bold yellow]"
        )
        for name, doc in docs.items():
            console.print(f"  - Upsert {len(doc.get('items', []))} {name}.")
        return

    async with get_session() as session:
        async with session.begin():
            console.print("  -> Importing capabilities...")
            await _upsert_items(
                session, Capability, docs["capabilities"].get("items", []), ["id"]
            )

            console.print("  -> Importing symbols...")
            await _upsert_items(
                session, Symbol, docs["symbols"].get("items", []), ["id"]
            )

            console.print("  -> Importing links...")
            links_items = docs["links"].get("items", [])
            if links_items:
                await session.execute(text("DELETE FROM core.symbol_capability_links;"))
                await _upsert_items(
                    session,
                    SymbolCapabilityLink,
                    links_items,
                    ["symbol_id", "capability_id", "source"],
                )

            console.print("  -> Importing North Star...")
            await _upsert_items(
                session, Northstar, docs["northstar"].get("items", []), ["id"]
            )

    console.print(
        "[bold green]✅ Import complete. Database is synchronized with YAML files.[/bold green]"
    )


# --- Main Verify Logic ---
# ID: e1964902-4b8f-4154-974a-aed21d0abbcc
def run_verify():
    """Checks digests of exported YAML files to ensure integrity."""
    if not EXPORT_DIR.exists():
        console.print(
            f"[bold red]Export directory not found: {EXPORT_DIR}. Cannot verify.[/bold red]"
        )
        return False

    console.print("🔐 Verifying digests of exported YAML files...")

    files_to_check = [
        "capabilities.yaml",
        "symbols.yaml",
        "links.yaml",
        "northstar.yaml",
    ]
    all_ok = True

    for filename in files_to_check:
        path = EXPORT_DIR / filename
        if not path.exists():
            console.print(
                f"  - [yellow]SKIP[/yellow]: [cyan]{filename}[/cyan] does not exist."
            )
            continue

        doc = read_yaml(path)
        items = doc.get("items", [])
        expected_digest = doc.get("digest")

        if not expected_digest:
            console.print(
                f"  - [red]FAIL[/red]: [cyan]{filename}[/cyan] is missing a digest."
            )
            all_ok = False
            continue

        actual_digest = compute_digest(items)

        if expected_digest == actual_digest:
            console.print(
                f"  - [green]PASS[/green]: [cyan]{filename}[/cyan] digest is valid."
            )
        else:
            console.print(
                f"  - [red]FAIL[/red]: [cyan]{filename}[/cyan] digest mismatch!"
            )
            all_ok = False

    if all_ok:
        console.print("[bold green]✅ All digests are valid.[/bold green]")
    else:
        console.print(
            "[bold red]❌ One or more digests failed verification.[/bold red]"
        )

    return all_ok
