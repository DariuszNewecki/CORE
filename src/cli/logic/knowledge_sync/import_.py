# src/cli/logic/knowledge_sync/import_.py
"""
Handles importing YAML files into the database for the CORE Working Mind.
"""

from __future__ import annotations

from typing import Any, Dict

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
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .utils import _get_items_from_doc, compute_digest, read_yaml

console = Console()
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"
YAML_FILES = {
    "capabilities": "capabilities.yaml",
    "symbols": "symbols.yaml",
    "links": "links.yaml",
    "northstar": "northstar.yaml",
    "cognitive_roles": "cognitive_roles.yaml",
    "resource_manifest": "resource_manifest.yaml",
}


async def _upsert_items(session, table_model, items, index_elements):
    """Generic upsert function for SSOT tables.

    Args:
        session: Database session.
        table_model: SQLAlchemy model class.
        items: List of items to upsert.
        index_elements: Columns to use for conflict resolution.
    """
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
    """Import capabilities into the database.

    Args:
        session: Database session.
        doc: YAML document containing capabilities.
    """
    console.print("  -> Importing capabilities...")
    await _upsert_items(session, Capability, doc.get("items", []), ["id"])


async def _import_symbols(session, doc: Dict[str, Any]) -> None:
    """Import symbols into the database, fixing missing symbol_path if necessary."""
    console.print("  -> Importing symbols...")
    items = doc.get("items", [])
    for item in items:
        if "symbol_path" not in item or not item["symbol_path"]:
            module = item.get("module")
            qualname = item.get("qualname")
            if module and qualname:
                file_path = "src/" + module.replace(".", "/") + ".py"
                item["symbol_path"] = f"{file_path}::{qualname}"

    await _upsert_items(session, Symbol, items, ["id"])


async def _import_links(session, doc: Dict[str, Any]) -> None:
    """Import symbol-capability links into the database.

    Args:
        session: Database session.
        doc: YAML document containing links.
    """
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
    """Import North Star mission into the database.

    Args:
        session: Database session.
        doc: YAML document containing North Star data.
    """
    console.print("  -> Importing North Star...")
    await _upsert_items(session, Northstar, doc.get("items", []), ["id"])


async def _import_llm_resources(session, doc: Dict[str, Any]) -> None:
    """Import LLM resources into the database.

    Args:
        session: Database session.
        doc: YAML document containing LLM resources.
    """
    console.print("  -> Importing LLM resources...")
    await _upsert_items(session, LlmResource, doc.get("llm_resources", []), ["name"])


async def _import_cognitive_roles(session, doc: Dict[str, Any]) -> None:
    """Import cognitive roles into the database.

    Args:
        session: Database session.
        doc: YAML document containing cognitive roles.
    """
    console.print("  -> Importing cognitive roles...")
    await _upsert_items(
        session, CognitiveRole, doc.get("cognitive_roles", []), ["role"]
    )


# ID: a5c43fa1-1137-426d-a98f-a8f0e9265cf7
async def run_import(dry_run: bool) -> None:
    """Imports YAML files into the database, with optional dry run.

    Args:
        dry_run: If True, prints actions without executing them.
    """
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
    for name, doc in docs.items():
        if "digest" in doc and "items" in doc:
            if doc["digest"] != compute_digest(doc["items"]):
                console.print(
                    f"[bold red]Digest mismatch in {name}.yaml! "
                    "Aborting import. Run 'snapshot' to regenerate.[/bold red]"
                )
                return

    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: The following actions would be taken --[/bold yellow]"
        )
        for name, doc in docs.items():
            count = len(_get_items_from_doc(doc, name))
            console.print(f"  - Upsert {count} {name}.")
        return

    async with get_session() as session:
        async with session.begin():
            await _import_capabilities(session, docs["capabilities"])
            await _import_symbols(session, docs["symbols"])
            await _import_links(session, docs["links"])
            await _import_northstar(session, docs["northstar"])
            await _import_llm_resources(session, docs["resource_manifest"])
            await _import_cognitive_roles(session, docs["cognitive_roles"])

    console.print(
        "[bold green]✅ Import complete. Database is synchronized with YAML files.[/bold green]"
    )
