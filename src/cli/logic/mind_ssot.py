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
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from rich.console import Console
from services.database.models import (
    Capability,
    CognitiveRole,
    LlmResource,
    Northstar,
    Symbol,
    SymbolCapabilityLink,
)
from services.database.session_manager import get_session
from shared.config import settings
from shared.time import now_iso
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

console = Console()
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"

# Configuration
YAML_FILES = {
    "capabilities": "capabilities.yaml",
    "symbols": "symbols.yaml",
    "links": "links.yaml",
    "northstar": "northstar.yaml",
    "cognitive_roles": "cognitive_roles.yaml",
    "resource_manifest": "resource_manifest.yaml",
}

SNAPSHOT_FILES = ["capabilities", "symbols", "links", "northstar"]


# --- Helper Functions ---


# ID: f8fbb8f3-eda9-4104-8bc3-a15f0dfa5e50
def canonicalize(obj: Any) -> Any:
    """Recursively sorts dictionary keys to ensure a stable, consistent order for hashing."""
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        if all(isinstance(i, dict) for i in obj):
            try:
                sort_key = next(
                    (k for k in ("id", "name", "key", "role") if k in obj[0]), None
                )
                if sort_key:
                    return sorted(obj, key=lambda x: str(x.get(sort_key, "")))
            except (TypeError, IndexError):
                pass
        return [canonicalize(x) for x in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


# ID: c93917a5-b94c-4b96-9eae-60fae47985d7
def compute_digest(items: List[Dict[str, Any]]) -> str:
    """Creates a unique fingerprint (SHA256) for a list of items."""
    canon = canonicalize(items)
    payload = json.dumps(
        canon, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


# ID: 96700d48-c9d8-4ebd-ae3f-8a6fdd157f52
def write_yaml(path: Path, items: List[Dict[str, Any]], exported_at: str) -> str:
    """Writes a list of items to a YAML file, including version, timestamp, and the unique digest."""
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


def _convert_uuids_in_items(items: List[Dict[str, Any]]) -> None:
    """Convert string UUIDs back to UUID objects in-place."""
    for item in items:
        for key in ["id", "symbol_id", "capability_id"]:
            if key in item and isinstance(item[key], str):
                try:
                    item[key] = uuid.UUID(item[key])
                except (ValueError, TypeError):
                    pass


# ID: b38101f8-4d92-4a95-82f5-da010176ab8a
def read_yaml(path: Path) -> Dict[str, Any]:
    """Reads a YAML file and returns its content, handling missing files."""
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Find the items key and convert UUIDs
    items_key = next(
        (k for k in ["items", "llm_resources", "cognitive_roles"] if k in data),
        None,
    )

    if items_key and isinstance(data.get(items_key), list):
        _convert_uuids_in_items(data[items_key])

    return data


def _get_diff_links_key(item: Dict[str, Any]) -> str:
    """Creates a stable composite key for a link dictionary."""
    return f"{str(item.get('symbol_id', ''))}-{str(item.get('capability_id', ''))}-{item.get('source', '')}"


def _get_items_from_doc(doc: Dict[str, Any], doc_name: str) -> List[Dict[str, Any]]:
    """Extract items from a document using the appropriate key."""
    possible_keys = [doc_name, "items", "llm_resources", "cognitive_roles"]
    items_key = next((k for k in possible_keys if k in doc), None)
    return doc.get(items_key, []) if items_key else []


# --- Database Fetcher Functions ---


# ID: 530dff8c-42fa-4211-99f1-e0f7421c6c1f
async def fetch_capabilities() -> List[Dict[str, Any]]:
    """Reads all capabilities from the database, ordered consistently."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, name, objective, owner, domain, tags, status "
                "FROM core.capabilities ORDER BY lower(domain), lower(name), id"
            )
        )
        return [dict(row._mapping) for row in result]


# ID: 59794634-4778-4fff-8be1-cad2ea0297f5
async def fetch_symbols() -> List[Dict[str, Any]]:
    """Reads all symbols from the database, ordered consistently."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, module, qualname, kind, ast_signature, fingerprint, state "
                "FROM core.symbols ORDER BY fingerprint, id"
            )
        )
        return [dict(row._mapping) for row in result]


# ID: 755c8426-0a13-4cb0-8057-aaf57f45072b
async def fetch_links() -> List[Dict[str, Any]]:
    """Reads all symbol-capability links from the database, ordered consistently."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT symbol_id, capability_id, confidence, source, verified "
                "FROM core.symbol_capability_links "
                "ORDER BY capability_id, symbol_id, source"
            )
        )
        rows = [dict(row._mapping) for row in result]
        for r in rows:
            if "confidence" in r and r["confidence"] is not None:
                r["confidence"] = float(r["confidence"])
        return rows


# ID: 3eb9d6e7-2bcf-46b1-81c6-f8ed64f83ade
async def fetch_northstar() -> List[Dict[str, Any]]:
    """Reads the current North Star mission from the database."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, mission FROM core.northstar "
                "ORDER BY updated_at DESC LIMIT 1"
            )
        )
        return [dict(row._mapping) for row in result]


# --- Snapshot Logic ---


async def _record_snapshot_manifest(
    digests: List[Tuple[str, str]],
    who: str,
    env: str,
    note: str | None,
) -> None:
    """Record the snapshot manifest in the database."""
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "INSERT INTO core.export_manifests (who, environment, notes) "
                    "VALUES (:who, :env, :note) RETURNING id"
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


# ID: f9711c2e-e01d-4872-aa1b-3e46916bdd7f
async def run_snapshot(env: str | None, note: str | None):
    """The main function that performs the snapshot operation."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    exported_at = now_iso()
    who = getpass.getuser()
    env = env or "dev"

    console.print(f"📸 Creating a new snapshot of the database in '{EXPORT_DIR}'...")

    # Fetch all data
    caps, syms, links, north = await asyncio.gather(
        fetch_capabilities(), fetch_symbols(), fetch_links(), fetch_northstar()
    )

    # Write YAML files and collect digests
    snapshots = [
        ("capabilities.yaml", caps),
        ("symbols.yaml", syms),
        ("links.yaml", links),
        ("northstar.yaml", north),
    ]

    digests = [
        (filename, write_yaml(EXPORT_DIR / filename, data, exported_at))
        for filename, data in snapshots
    ]

    # Record in database
    await _record_snapshot_manifest(digests, who, env, note)

    console.print("[bold green]✅ Snapshot complete.[/bold green]")
    for filename, sha in digests:
        console.print(f"  - Wrote '{filename}' with digest: {sha}")


# --- Diff Logic ---


# ID: 4bba60c1-0edc-40e9-9b63-db1b8260232b
def diff_sets(
    db_items: List[Dict[str, Any]], file_items: List[Dict[str, Any]], key: str
) -> Dict[str, Any]:
    """Compares two lists of dictionaries based on a key and returns the differences."""
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


# ID: 927db8f4-84c3-419f-b949-7dec1c001729
async def run_diff(as_json: bool):
    """Orchestrates the diff operation."""
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


# --- Import Logic ---


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


async def _import_capabilities(session, doc: Dict[str, Any]) -> None:
    """Import capabilities into the database."""
    console.print("  -> Importing capabilities...")
    await _upsert_items(session, Capability, doc.get("items", []), ["id"])


async def _import_symbols(session, doc: Dict[str, Any]) -> None:
    """Import symbols into the database."""
    console.print("  -> Importing symbols...")
    await _upsert_items(session, Symbol, doc.get("items", []), ["id"])


async def _import_links(session, doc: Dict[str, Any]) -> None:
    """Import symbol-capability links into the database."""
    console.print("  -> Importing links...")
    links_items = doc.get("items", [])
    if links_items:
        await session.execute(text("DELETE FROM core.symbol_capability_links;"))
        await _upsert_items(
            session,
            SymbolCapabilityLink,
            links_items,
            ["symbol_id", "capability_id", "source"],
        )


async def _import_northstar(session, doc: Dict[str, Any]) -> None:
    """Import North Star mission into the database."""
    console.print("  -> Importing North Star...")
    await _upsert_items(session, Northstar, doc.get("items", []), ["id"])


async def _import_llm_resources(session, doc: Dict[str, Any]) -> None:
    """Import LLM resources into the database."""
    console.print("  -> Importing LLM resources...")
    await _upsert_items(session, LlmResource, doc.get("llm_resources", []), ["name"])


async def _import_cognitive_roles(session, doc: Dict[str, Any]) -> None:
    """Import cognitive roles into the database."""
    console.print("  -> Importing cognitive roles...")
    await _upsert_items(
        session, CognitiveRole, doc.get("cognitive_roles", []), ["role"]
    )


async def _perform_import(docs: Dict[str, Dict[str, Any]]) -> None:
    """Perform the actual database import."""
    async with get_session() as session:
        async with session.begin():
            await _import_capabilities(session, docs["capabilities"])
            await _import_symbols(session, docs["symbols"])
            await _import_links(session, docs["links"])
            await _import_northstar(session, docs["northstar"])
            await _import_llm_resources(session, docs["resource_manifest"])
            await _import_cognitive_roles(session, docs["cognitive_roles"])


def _verify_digests(docs: Dict[str, Dict[str, Any]]) -> bool:
    """Verify digests for documents that contain them."""
    for name, doc in docs.items():
        if "digest" in doc and "items" in doc:
            if doc["digest"] != compute_digest(doc["items"]):
                console.print(
                    f"[bold red]Digest mismatch in {name}.yaml! "
                    "Aborting import. Run 'snapshot' to regenerate.[/bold red]"
                )
                return False
    return True


def _print_dry_run_summary(docs: Dict[str, Dict[str, Any]]) -> None:
    """Print what would happen in a dry run."""
    console.print(
        "[bold yellow]-- DRY RUN: The following actions would be taken --[/bold yellow]"
    )
    for name, doc in docs.items():
        count = len(_get_items_from_doc(doc, name))
        console.print(f"  - Upsert {count} {name}.")


# ID: 63b88848-dccb-45a9-88bc-b5151b4d4767
async def run_import(dry_run: bool):
    """Orchestrates the import operation."""
    if not EXPORT_DIR.exists():
        console.print(
            f"[bold red]Export directory not found: {EXPORT_DIR}. Cannot import.[/bold red]"
        )
        return

    # Load all YAML documents
    docs = {
        name: read_yaml(EXPORT_DIR / filename) for name, filename in YAML_FILES.items()
    }

    # Verify digests for files that have them
    if not _verify_digests(docs):
        return

    if dry_run:
        _print_dry_run_summary(docs)
        return

    await _perform_import(docs)
    console.print(
        "[bold green]✅ Import complete. Database is synchronized with YAML files.[/bold green]"
    )


# --- Verify Logic ---


# ID: da45c167-d04b-458d-8776-e144d55b01ad
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
