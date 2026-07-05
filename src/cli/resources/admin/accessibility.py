# src/cli/resources/admin/accessibility.py
"""
``core-admin admin accessibility`` — derived census of every CLI command
and API route classified by exposure tier.

Reads @command_meta.exposure (CLI) and ROUTER_EXPOSURE module constants
(API). Never hand-maintained — the metadata is authoritative (ADR-110 D5).
"""

from __future__ import annotations

import importlib

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
    get_command_meta,
)

from .hub import app


console = Console()


_API_ROUTE_MODULES: list[str] = [
    "api.v1.audit_routes",
    "api.v1.census_routes",
    "api.v1.coverage_routes",
    "api.v1.daemon_routes",
    "api.v1.development_routes",
    "api.v1.fix_routes",
    "api.v1.inspect_routes",
    "api.v1.integration_routes",
    "api.v1.integrity_routes",
    "api.v1.knowledge_routes",
    "api.v1.lane_routes",
    "api.v1.lint_routes",
    "api.v1.proposals_routes",
    "api.v1.quality_routes",
    "api.v1.refactor_routes",
    "api.v1.sync_routes",
]


@app.command("accessibility")
@command_meta(
    canonical_name="admin.accessibility",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Show exposure classification for all CLI commands and API routes (ADR-110 D5)",
)
@core_command(dangerous=False, requires_context=False)
# ID: 2629c5b6-dec5-4708-b30b-a40a28898093
async def accessibility_cmd(
    tier: str | None = typer.Option(
        None,
        "--tier",
        help="Filter by exposure tier: user-facing or governor-only",
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        help="Output format: table or json",
    ),
) -> None:
    """
    Derived census of CLI command and API route exposure classifications.
    Read from @command_meta.exposure and ROUTER_EXPOSURE module constants.
    Filter with --tier user-facing or --tier governor-only.
    """
    import json as _json
    from typing import cast

    from cli.admin_cli import app as main_app
    from shared.cli.app_introspection import walk_typer_app
    from shared.protocols.typer_protocols import TyperAppLike

    # ── CLI commands ──────────────────────────────────────────────────────────
    all_cmds = walk_typer_app(cast(TyperAppLike, main_app))
    cli_rows: list[tuple[str, str, str, str]] = []
    for cmd in all_cmds:
        callback = cmd.get("callback")
        meta = get_command_meta(callback) if callback else None
        exposure_val = (
            meta.exposure.value
            if meta and hasattr(meta, "exposure")
            else CommandExposure.GOVERNOR_ONLY.value
        )
        if tier and exposure_val != tier:
            continue
        cli_rows.append(
            (cmd["name"], exposure_val, cmd.get("behavior", ""), cmd.get("layer", ""))
        )

    # ── API routes ────────────────────────────────────────────────────────────
    api_rows: list[tuple[str, str]] = []
    for mod_name in _API_ROUTE_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as exc:
            console.print(f"[yellow]warn:[/yellow] could not import {mod_name}: {exc}")
            continue
        exposure_val = getattr(mod, "ROUTER_EXPOSURE", "unknown")
        route_label = mod_name.removeprefix("api.v1.")
        if tier and exposure_val != tier:
            continue
        api_rows.append((route_label, exposure_val))

    # ── Output ────────────────────────────────────────────────────────────────
    if output_format == "json":
        out = {
            "cli": [
                {"name": r[0], "exposure": r[1], "behavior": r[2], "layer": r[3]}
                for r in sorted(cli_rows)
            ],
            "api": [{"route": r[0], "exposure": r[1]} for r in sorted(api_rows)],
        }
        console.print(_json.dumps(out, indent=2))
        return

    cli_table = Table(
        title="CLI Commands — Exposure Classification", show_header=True, expand=False
    )
    cli_table.add_column("Command", style="cyan", no_wrap=True)
    cli_table.add_column("Exposure", style="bold")
    cli_table.add_column("Behavior")
    cli_table.add_column("Layer")
    for name, exposure, behavior, layer in sorted(cli_rows):
        style = "green" if exposure == "user-facing" else "yellow"
        cli_table.add_row(name, f"[{style}]{exposure}[/{style}]", behavior, layer)
    console.print(cli_table)

    api_table = Table(
        title="API Routes — Exposure Classification", show_header=True, expand=False
    )
    api_table.add_column("Route Module", style="cyan", no_wrap=True)
    api_table.add_column("Exposure", style="bold")
    for route, exposure in sorted(api_rows):
        style = "green" if exposure == "user-facing" else "yellow"
        api_table.add_row(route, f"[{style}]{exposure}[/{style}]")
    console.print(api_table)
