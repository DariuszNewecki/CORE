# src/cli/commands/check/quality.py
"""
Code quality and system health commands.

Thin clients over the /v1/quality namespace (ADR-055 D3). lint and
tests are async (subprocess-backed); system bundles lint+tests+audit.
"""

from __future__ import annotations

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command


console = Console()


async def _poll_quality(client: CoreApiClient, label: str, initial: dict) -> dict:
    """Poll an async /quality dispatch to terminal status, raising on failure."""
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]{label} failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]{label} failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)
    return final


@core_command(dangerous=False)
# ID: 23a0948a-570d-442d-b19a-ebd3af4f1c2d
async def lint_cmd(ctx: typer.Context) -> None:
    """
    Check code formatting and quality using Black and Ruff.
    """
    _ = ctx
    client = CoreApiClient()
    initial = await client.quality_lint()
    await _poll_quality(client, "quality.lint", initial)
    console.print("[green]✓ lint completed.[/green]")


@core_command(dangerous=False)
# ID: 3e9af575-9c8b-483d-b63a-477e5c6b0a02
async def tests_cmd(ctx: typer.Context) -> None:
    """
    Run the project test suite via pytest.
    """
    _ = ctx
    client = CoreApiClient()
    initial = await client.quality_tests()
    await _poll_quality(client, "quality.tests", initial)
    console.print("[green]✓ tests completed.[/green]")


@core_command(dangerous=False)
# ID: fdb8e693-c147-469a-a17a-1ee59227985b
async def system_cmd(ctx: typer.Context) -> None:
    """
    Run all system health checks: Lint, Tests, and Constitutional Audit.
    """
    _ = ctx
    client = CoreApiClient()
    console.rule("[bold cyan]System Health Bundle (lint + tests + audit)[/bold cyan]")
    initial = await client.quality_system()
    await _poll_quality(client, "quality.system", initial)
    console.print("[green]✓ system health bundle completed.[/green]")
