# src/cli/resources/cognitive_roles/project.py
"""
core-admin cognitive-roles diff / project — #821 Unit 2.

Compares .intent/taxonomies/cognitive_roles.yaml's required_capabilities
against core.cognitive_roles and, with --apply, projects YAML into the DB.
Explicit and on-demand only — no scheduled/startup reconciliation
(ADR-090 D1).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


console = Console()


# ID: a9f4c2e7-3b1d-4a8f-9c6e-2d7f1a4b8c3e
def _render_projection(data: dict) -> None:
    """Render a project.cognitive_roles ActionResult.data payload."""
    if data.get("in_sync"):
        console.print(
            "[bold green]core.cognitive_roles is in sync with "
            "cognitive_roles.yaml[/bold green]"
        )

    drift = data.get("drift") or []
    if drift:
        table = Table(title="Capability drift")
        table.add_column("role")
        table.add_column("yaml capabilities")
        table.add_column("db capabilities")
        for entry in drift:
            table.add_row(
                entry["role"],
                ", ".join(entry["yaml_capabilities"]),
                ", ".join(entry["db_capabilities"]),
            )
        console.print(table)

    for label, key in (
        ("DB-only roles (reported, not deleted)", "db_only_roles"),
        ("YAML-only roles (reported, not inserted)", "yaml_only_roles"),
    ):
        values = data.get(key) or []
        if values:
            console.print(f"[yellow]{label}:[/yellow] {', '.join(values)}")

    non_canonical = data.get("non_canonical") or []
    if non_canonical:
        console.print(
            "[bold red]Non-canonical YAML capability values "
            "(blocked from apply):[/bold red]"
        )
        for entry in non_canonical:
            console.print(f"  - {entry['role']}: {', '.join(entry['capabilities'])}")


@app.command(
    "diff", help="Read-only comparison of cognitive_roles.yaml vs core.cognitive_roles."
)
@core_command(dangerous=False, requires_context=False)
# ID: b3e8d1a6-4c9f-4b2e-8a7d-1e3c5f9a2b6d
async def cognitive_roles_diff(ctx: typer.Context) -> None:
    """Print capability drift; exits 1 if not in sync (CI-gate friendly)."""
    client = CoreApiClient()
    response = await client.cognitive_roles.project(write=False)
    data = response.get("data", {})
    _render_projection(data)
    if not data.get("in_sync", False):
        raise typer.Exit(1)


@app.command(
    "project",
    help="Project cognitive_roles.yaml capabilities into core.cognitive_roles.",
)
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: c7f2a9d4-5b1e-4c8a-9f3d-6a2e8b4c1f7d
async def cognitive_roles_project(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write the projection to core.cognitive_roles (otherwise behaves like diff).",
    ),
) -> None:
    """Without --apply: same as `diff`. With --apply: performs the governed write."""
    client = CoreApiClient()
    response = await client.cognitive_roles.project(write=apply)
    data = response.get("data", {})
    _render_projection(data)

    if not apply:
        console.print("[yellow]Dry-run: pass --apply to write the projection.[/yellow]")
        return

    applied = data.get("applied") or []
    blocked = data.get("blocked") or []
    if applied:
        console.print(f"[bold green]Applied:[/bold green] {', '.join(applied)}")
    if blocked:
        console.print(
            f"[bold red]Blocked (non-canonical, not written):[/bold red] "
            f"{', '.join(blocked)}"
        )
