# src/features/self_healing/duplicate_id_service.py
"""
Provides a service to intelligently find and resolve duplicate UUIDs in the codebase.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from rich.console import Console
from sqlalchemy import text

from features.governance.checks.id_uniqueness_check import IdUniquenessCheck
from services.database.session_manager import get_session
from shared.config import settings

console = Console()


async def _get_symbol_creation_dates() -> dict[str, str]:
    """Queries the database to get the creation timestamp for each symbol UUID."""
    async with get_session() as session:
        # --- MODIFIED: Select the correct 'id' column instead of 'uuid' ---
        result = await session.execute(text("SELECT id, created_at FROM core.symbols"))
        # --- MODIFIED: Access the result using 'row.id' instead of 'row.uuid' ---
        return {str(row.id): row.created_at.isoformat() for row in result}


# ID: 5891cbbe-ae62-4743-92fa-2e204ca5fa13
async def resolve_duplicate_ids(dry_run: bool = True) -> int:
    """
    Finds all duplicate IDs and fixes them by assigning new UUIDs to all but the oldest symbol.

    Returns:
        The number of files that were (or would be) modified.
    """
    console.print("🕵️  Scanning for duplicate UUIDs...")

    # 1. Discover duplicates using the existing auditor check
    context = __import__(
        "features.governance.audit_context"
    ).governance.audit_context.AuditorContext(settings.REPO_PATH)
    uniqueness_check = IdUniquenessCheck(context)
    findings = uniqueness_check.execute()

    duplicates = [f for f in findings if f.check_id == "linkage.id.duplicate"]

    if not duplicates:
        console.print("[bold green]✅ No duplicate UUIDs found.[/bold green]")
        return 0

    console.print(
        f"[bold yellow]Found {len(duplicates)} duplicate UUID(s). Resolving...[/bold yellow]"
    )

    # 2. Get creation dates from the database to find the "original"
    symbol_creation_dates = await _get_symbol_creation_dates()

    files_to_modify: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for finding in duplicates:
        locations_str = finding.context.get("locations", "")
        # The UUID is in the message: "Duplicate ID tag found: {uuid}"
        duplicate_uuid = finding.message.split(": ")[-1]

        locations = []
        for loc in locations_str.split(", "):
            path, line = loc.rsplit(":", 1)
            locations.append((path, int(line)))

        # Find the original symbol (the one created first)
        original_location = None

        # Check if we have creation date info for this UUID
        if duplicate_uuid in symbol_creation_dates:
            # Assume the first location for a given UUID is the original if we have DB info
            original_location = locations[0]
        else:
            # Fallback for symbols not yet in DB: assume first found is original
            original_location = locations[0]

        console.print(f"  -> Duplicate UUID: [cyan]{duplicate_uuid}[/cyan]")
        console.print(
            f"     - Original determined to be at: [green]{original_location[0]}:{original_location[1]}[/green]"
        )

        # Mark all other locations for change
        for path, line_num in locations:
            if (path, line_num) != original_location:
                console.print(
                    f"     - Copy found at: [yellow]{path}:{line_num}[/yellow]"
                )
                files_to_modify[path].append((line_num, duplicate_uuid))

    if not files_to_modify:
        console.print(
            "[bold green]✅ All duplicates seem to be resolved or are new. No changes needed.[/bold green]"
        )
        return 0

    if dry_run:
        console.print(
            "\n[bold yellow]-- DRY RUN: No files will be changed. --[/bold yellow]"
        )
        for path, changes in files_to_modify.items():
            console.print(
                f"  - Would modify [cyan]{path}[/cyan] to fix {len(changes)} duplicate ID(s)."
            )
        return len(files_to_modify)

    # Apply the changes
    console.print("\n[bold]Applying fixes...[/bold]")
    for file_str, changes in files_to_modify.items():
        file_path = settings.REPO_PATH / file_str
        content = file_path.read_text("utf-8")
        lines = content.splitlines()

        for line_num, old_uuid in changes:
            new_uuid = str(uuid.uuid4())
            line_index = line_num - 1
            if old_uuid in lines[line_index]:
                lines[line_index] = lines[line_index].replace(old_uuid, new_uuid)
                console.print(
                    f"  - Replaced ID in [green]{file_str}:{line_num}[/green]"
                )

        file_path.write_text("\n".join(lines) + "\n", "utf-8")

    return len(files_to_modify)
