# src/cli/resources/plugin/list_plugins.py
"""`core-admin plugin list` (ADR-177 D8): the plug-ins CORE loads."""

from __future__ import annotations

import json
import sys

import typer

from body.services.plugin_check import list_installed_plugins
from cli.utils import core_command

from . import app


@app.command("list")
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 4e619b01-cf83-4fde-b55d-91a83d56cc5a
async def list_command(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "text", "--format", help="`text` (default) or `json`."
    ),
) -> None:
    """List the installed plug-ins CORE loads, with version and fingerprint.

    A plug-in that fails its manifest checks is not listed; run
    `core-admin plugin check <name>` to see why.

    Examples:
        core-admin plugin list
        core-admin plugin list --format json
    """
    if output_format not in ("text", "json"):
        typer.echo(f"--format must be text or json (got {output_format!r})", err=True)
        raise typer.Exit(3)
    plugins = list_installed_plugins()
    if output_format == "json":
        rows = [
            {
                "name": p.name,
                "version": p.version,
                "core_engine_api": p.core_engine_api,
                "engines": [getattr(e, "engine_id", e.__name__) for e in p.engines],
                "catalogs": str(p.catalogs) if p.catalogs else None,
                "packs": str(p.packs) if p.packs else None,
                "fingerprint": p.fingerprint,
            }
            for p in plugins
        ]
        sys.stdout.write(json.dumps(rows, indent=2) + "\n")
        return
    if not plugins:
        typer.echo("No plug-ins installed.")
        return
    for p in plugins:
        engines = ", ".join(getattr(e, "engine_id", e.__name__) for e in p.engines)
        typer.echo(f"{p.label}  core_engine_api {p.core_engine_api}  {p.fingerprint}")
        typer.echo(f"  engines: {engines or 'none'}")
        typer.echo(f"  catalogs: {p.catalogs or 'none'}")
        typer.echo(f"  packs: {p.packs or 'none'}")
