# src/cli/commands/status.py
"""Status command group.

Golden Path:
- status drift {guard|symbol|vector|all}

All drift scopes route to /v1/status/drift (ADR-057 D3) plus the local
`cli.commands.guard.guard_drift_cmd` for the manifest-vs-code guard
check. No imports from `mind.*` — that was a layer inversion on the old
status path.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()
status_app = typer.Typer(
    help="Single-glance system state and readiness.", no_args_is_help=True
)


def _warn_not_wired(detail: str) -> None:
    typer.secho(f"STATUS: not fully wired yet ({detail})", fg=typer.colors.YELLOW)


@status_app.command("drift")
@core_command(dangerous=False, requires_context=False)
# ID: 17ba54ad-6d9e-4392-9512-7b62053575ea
async def drift_cmd(
    ctx: typer.Context,
    scope: str = typer.Argument("all", help="Drift scope: guard|symbol|vector|all"),
) -> None:
    """Consolidated drift entry point."""
    _ = ctx
    scope_norm = (scope or "all").strip().lower()
    if scope_norm not in {"guard", "symbol", "vector", "all"}:
        typer.secho(
            f"Invalid scope '{scope}'. Use: guard|symbol|vector|all",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)

    client = CoreApiClient()

    # ID: 76621d1c-d1a8-4b47-8210-3c969bc138f1
    async def run_guard() -> None:
        console.print("[bold]Drift: guard[/bold]")
        try:
            from cli.commands.guard import run_guard_drift
        except Exception as exc:
            logger.debug("status drift: cannot import run_guard_drift: %s", exc)
            _warn_not_wired("guard drift handler not available")
            return
        await run_guard_drift()

    # ID: 54d8b8dd-0ea6-4199-bcc3-0b68fb356c79
    async def run_symbol_or_vector(api_scope: str) -> None:
        console.print(f"[bold]Drift: {api_scope}[/bold]")
        payload = await client.status_drift(scope=api_scope)
        console.print(payload)

    if scope_norm == "guard":
        await run_guard()
        return
    if scope_norm == "symbol":
        await run_symbol_or_vector("symbols")
        return
    if scope_norm == "vector":
        await run_symbol_or_vector("vectors")
        return

    # scope == "all"
    await run_guard()
    console.print()
    await run_symbol_or_vector("symbols")
    console.print()
    await run_symbol_or_vector("vectors")
