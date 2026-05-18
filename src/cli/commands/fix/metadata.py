# src/cli/commands/fix/metadata.py
"""
Metadata-related self-healing commands for the 'fix' CLI group.

Provides:
- fix ids (Assign stable UUIDs)
- fix purge-legacy-tags
- fix policy-ids
- fix tags (Capability tagging)
- fix duplicate-ids
- fix placeholders
- fix dead-code

Thin clients over POST /v1/fix/run/{fix_id}. All execution moves
server-side; this module only dispatches, polls, and renders.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


__all__ = [
    "fix_dead_code_cmd",
    "fix_duplicate_ids_command",
    "fix_placeholders_command",
    "fix_policy_ids_command",
    "fix_tags_command",
    "purge_legacy_tags_command",
]


async def _dispatch_and_poll(
    fix_id: str, *, write: bool, params: dict | None = None
) -> dict:
    """Dispatch an atomic fix and poll to terminal status.

    Returns the final fix_runs payload. Raises typer.Exit(1) on
    dispatch failure or non-completed terminal status.
    """
    client = CoreApiClient()
    initial = await client.run_fix(fix_id, write=write, params=params)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]{fix_id} failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]{fix_id} failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)
    return final


@fix_app.command(
    "purge-legacy-tags",
    help="Removes obsolete tag formats (e.g. old 'Tag:' or 'Metadata:' lines).",
)
@core_command(dangerous=True, confirmation=True)
# ID: ab1c0d74-ec6c-45b4-a909-2a43eb9b8d41
async def purge_legacy_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes (remove the lines)."
    ),
) -> None:
    """Remove obsolete tag formats from Python files."""
    _ = ctx
    final = await _dispatch_and_poll("fix.purge_legacy_tags", write=write)
    data = (final.get("result") or {}).get("data", {})
    removed = data.get("removed", 0)
    mode = "removed" if write else "would be removed (dry-run)"
    console.print(f"[bold green]Obsolete tags {mode}: {removed}[/bold green]")


@fix_app.command(
    "policy-ids", help="Assigns missing IDs to policy files in .intent/policies/."
)
@core_command(dangerous=True, confirmation=True)
# ID: d17af23d-3b5a-4372-bf6a-efeef7f15c03
async def fix_policy_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Write the IDs to the policy files."
    ),
    policies_dir: Path = typer.Option(
        Path(".intent/policies"), help="Path to the policies directory."
    ),
) -> None:
    """Ensure each policy file has a unique policy_id."""
    _ = ctx
    _ = policies_dir
    final = await _dispatch_and_poll("fix.policy_ids", write=write)
    data = (final.get("result") or {}).get("data", {})
    added = data.get("added", 0)
    mode = "write" if write else "dry-run"
    console.print(f"[bold green]Policy IDs: added={added} ({mode})[/bold green]")


@fix_app.command(
    "tags", help="Tags untagged capabilities by calling the capability-tagging service."
)
@core_command(dangerous=True, confirmation=True)
# ID: 7d415daf-34de-4971-be89-991cd9490591
async def fix_tags_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Write capability tags to DB."),
) -> None:
    """
    Automatically tag untagged capabilities using the AI naming agent.
    """
    _ = ctx
    await _dispatch_and_poll("fix.capability_tagging", write=write)
    console.print("[green]✓ fix.capability_tagging completed.[/green]")


@fix_app.command(
    "duplicate-ids",
    help="Resolves duplicate IDs by regenerating fresh UUIDs for conflicts.",
)
@core_command(dangerous=True, confirmation=True)
# ID: 96717df8-d28f-4124-bc1e-71bf3921b358
async def fix_duplicate_ids_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to resolve duplicate IDs."
    ),
) -> None:
    """Detect and resolve duplicate IDs in Python files."""
    _ = ctx
    console.print("[cyan]Resolving duplicate IDs...[/cyan]")
    await _dispatch_and_poll("fix.duplicate_ids", write=write)
    console.print("[green]✓ fix.duplicate_ids completed.[/green]")


@fix_app.command(
    "placeholders",
    help="Automated replacement of forbidden placeholders (FUTURE, pending, none).",
)
@core_command(dangerous=True, confirmation=True)
# ID: e8c8f803-1cad-4150-9e66-e50859d8bd35
async def fix_placeholders_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to resolve forbidden placeholders."
    ),
) -> None:
    """
    Detects and resolves forbidden placeholder strings (pending, FUTURE, etc.)
    via the registered fix.placeholders atomic action.
    """
    _ = ctx
    console.print("[cyan]Purging forbidden placeholders...[/cyan]")
    await _dispatch_and_poll("fix.placeholders", write=write)
    console.print("[green]✓ fix.placeholders completed.[/green]")


@fix_app.command(
    "dead-code", help="Mechanically remove unused variables/functions found by Vulture."
)
@core_command(dangerous=True)
# ID: d2a428ee-63c2-4212-8c73-5bbebf514ff0
async def fix_dead_code_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply the deletions."),
) -> None:
    """CLI wrapper for the Vulture Healer (registered as fix.vulture_heal)."""
    _ = ctx
    console.print("[bold cyan]Snipping dead code scars...[/bold cyan]")
    await _dispatch_and_poll("fix.vulture_heal", write=write)
    if not write:
        console.print(
            "\n[yellow]💡 Dry run complete. Use --write to apply the 'Scissors'.[/yellow]"
        )
