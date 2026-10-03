# src/cli/resources/cognitive_roles/project.py
"""
core-admin cognitive-roles sync — #821 Unit 2.

Compares .intent/taxonomies/cognitive_roles.yaml's required_capabilities
against core.cognitive_roles and, with --write, projects YAML into the DB.
Explicit and on-demand only — no scheduled/startup reconciliation
(ADR-090 D1).

`diff` and `project --apply` are the pre-2.12 names, kept as hidden,
deprecated aliases for one release (renaming a command users call is
breaking under the semver policy).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

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


async def _sync(*, write: bool, fail_on_drift: bool) -> None:
    client = CoreApiClient()
    response = await client.cognitive_roles.project(write=write)
    data = response.get("data", {})
    _render_projection(data)

    if not write:
        if not data.get("in_sync", False):
            console.print(
                "[yellow]Dry-run: pass --write to apply the projection.[/yellow]"
            )
            if fail_on_drift:
                raise typer.Exit(1)
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


@app.command(
    "sync",
    help=(
        "Compare cognitive_roles.yaml with core.cognitive_roles; "
        "with --write, project the YAML capabilities into the database."
    ),
)
@command_meta(
    canonical_name="cognitive-roles.sync",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Compare or project cognitive-role capabilities (YAML -> DB).",
    dangerous=True,
)
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: ec6fd20c-78b3-4509-9669-a92737a83f18
async def cognitive_roles_sync(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Write the projection to core.cognitive_roles (default: show drift only).",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the confirmation prompt for --write."
    ),
) -> None:
    """Without --write: show drift and exit 1 if out of sync (CI-gate friendly).
    With --write: perform the governed write."""
    await _sync(write=write, fail_on_drift=True)


@app.command(
    "diff",
    hidden=True,
    help="Deprecated: use `cognitive-roles sync`.",
)
@core_command(dangerous=False, requires_context=False)
# ID: b3e8d1a6-4c9f-4b2e-8a7d-1e3c5f9a2b6d
async def cognitive_roles_diff(ctx: typer.Context) -> None:
    """Deprecated alias for `cognitive-roles sync` (show drift; exit 1 if out of sync)."""
    console.print(
        "[yellow]`cognitive-roles diff` is deprecated; use `cognitive-roles sync`.[/yellow]"
    )
    await _sync(write=False, fail_on_drift=True)


@app.command(
    "project",
    hidden=True,
    help="Deprecated: use `cognitive-roles sync --write`.",
)
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: c7f2a9d4-5b1e-4c8a-9f3d-6a2e8b4c1f7d
async def cognitive_roles_project(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Deprecated spelling of `cognitive-roles sync --write`.",
    ),
) -> None:
    """Deprecated alias for `cognitive-roles sync [--write]` (pre-2.12 behaviour kept)."""
    console.print(
        "[yellow]`cognitive-roles project` is deprecated; "
        "use `cognitive-roles sync [--write]`.[/yellow]"
    )
    await _sync(write=apply, fail_on_drift=False)
