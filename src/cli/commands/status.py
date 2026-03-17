# src/cli/commands/status.py
"""
Status command group.

Golden Path:
- status drift {guard|symbol|vector|all}

Design:
- Tier 1 interface: operator-friendly, low ambiguity.
- Delegates work to existing implementations (no duplicate logic).
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()
status_app = typer.Typer(
    help="Single-glance system state and readiness.", no_args_is_help=True
)


def _warn_not_wired(detail: str) -> None:
    typer.secho(f"STATUS: not fully wired yet ({detail})", fg=typer.colors.YELLOW)


async def _maybe_await(result: Any) -> None:
    if hasattr(result, "__await__"):
        await result


@status_app.command("drift")
@core_command(dangerous=False)
# ID: 17ba54ad-6d9e-4392-9512-7b62053575ea
async def drift_cmd(
    ctx: typer.Context,
    scope: str = typer.Argument("all", help="Drift scope: guard|symbol|vector|all"),
) -> None:
    """
    Consolidated drift entry point.

    Consolidation target:
    - inspect guard drift     -> status drift guard
    - inspect symbol-drift    -> status drift symbol
    - inspect vector-drift    -> status drift vector
    - status drift all        -> consolidated output
    """
    scope_norm = (scope or "all").strip().lower()
    if scope_norm not in {"guard", "symbol", "vector", "all"}:
        typer.secho(
            f"Invalid scope '{scope}'. Use: guard|symbol|vector|all",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)
    try:
        from mind.enforcement.guard import guard_drift_cmd
    except Exception as exc:
        logger.debug("status drift: cannot import guard_drift_cmd: %s", exc)
        guard_drift_cmd = None
    try:
        from cli.commands import inspect as inspect_module
    except Exception as exc:
        logger.debug("status drift: cannot import inspect module: %s", exc)
        _warn_not_wired("cannot import cli.commands.inspect")
        raise typer.Exit(code=0)

    # ID: b17ebacd-4c58-4894-90eb-7cad3c95bbcf
    async def run_guard() -> None:
        logger.info("[bold]Drift: guard[/bold]")
        if guard_drift_cmd is None:
            _warn_not_wired("guard drift handler not available")
            return
        await _maybe_await(guard_drift_cmd())

    # ID: 145d4c27-7a19-4104-8874-06f2d765ed58
    async def run_symbol() -> None:
        logger.info("[bold]Drift: symbol[/bold]")
        fn = getattr(inspect_module, "symbol_drift_cmd", None)
        if not callable(fn):
            _warn_not_wired("inspect.symbol_drift_cmd not found")
            return
        fn(ctx)

    # ID: 24e7b157-b493-4ec0-9906-269f08fa9bdb
    async def run_vector() -> None:
        logger.info("[bold]Drift: vector[/bold]")
        fn = getattr(inspect_module, "vector_drift_command", None)
        if not callable(fn):
            _warn_not_wired("inspect.vector_drift_command not found")
            return
        await _maybe_await(fn(ctx))

    if scope_norm == "guard":
        await run_guard()
        return
    if scope_norm == "symbol":
        await run_symbol()
        return
    if scope_norm == "vector":
        await run_vector()
        return
    await run_guard()
    console.print()
    await run_symbol()
    console.print()
    await run_vector()
