# src/body/cli/commands/status.py

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
    help="Single-glance system state and readiness.",
    no_args_is_help=True,
)


def _warn_not_wired(detail: str) -> None:
    typer.secho(f"STATUS: not fully wired yet ({detail})", fg=typer.colors.YELLOW)


async def _maybe_await(result: Any) -> None:
    if hasattr(result, "__await__"):
        await result  # type: ignore[misc]


# ID: 7b2e5ad1-d6f6-4b84-9a5c-2b43d7a1fd9a
@status_app.command("drift")
@core_command(dangerous=False)
# ID: a115dadd-b7a5-431e-97d1-82d2a92ffad2
async def drift_cmd(
    ctx: typer.Context,
    scope: str = typer.Argument(
        "all",
        help="Drift scope: guard|symbol|vector|all",
    ),
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

    # Canonical implementations:
    # - Guard drift lives in mind.enforcement.guard_cli (async command).
    # - Symbol/vector drift live in inspect command module (existing logic).
    try:
        from mind.enforcement.guard_cli import guard_drift_cmd
    except Exception as exc:  # pragma: no cover
        logger.debug("status drift: cannot import guard_drift_cmd: %s", exc)
        guard_drift_cmd = None  # type: ignore[assignment]

    try:
        from cli.commands import inspect as inspect_module
    except Exception as exc:  # pragma: no cover
        logger.debug("status drift: cannot import inspect module: %s", exc)
        _warn_not_wired("cannot import cli.commands.inspect")
        raise typer.Exit(code=0)

    # ID: b5dbb533-7fe8-465f-bc13-c74c885c145e
    async def run_guard() -> None:
        console.print("[bold]Drift: guard[/bold]")
        if guard_drift_cmd is None:
            _warn_not_wired("guard drift handler not available")
            return
        # Use defaults from guard_cli (root='.', etc.)
        await _maybe_await(guard_drift_cmd())  # type: ignore[misc]

    # ID: 713f4631-e298-4fb9-a11e-7d77e7ebc472
    async def run_symbol() -> None:
        console.print("[bold]Drift: symbol[/bold]")
        fn = getattr(inspect_module, "symbol_drift_cmd", None)
        if not callable(fn):
            _warn_not_wired("inspect.symbol_drift_cmd not found")
            return
        fn(ctx)  # type: ignore[misc]

    # ID: 2875ccbe-184b-4ee3-85f8-6ab35be4048c
    async def run_vector() -> None:
        console.print("[bold]Drift: vector[/bold]")
        fn = getattr(inspect_module, "vector_drift_command", None)
        if not callable(fn):
            _warn_not_wired("inspect.vector_drift_command not found")
            return
        await _maybe_await(fn(ctx))  # type: ignore[misc]

    if scope_norm == "guard":
        await run_guard()
        return
    if scope_norm == "symbol":
        await run_symbol()
        return
    if scope_norm == "vector":
        await run_vector()
        return

    # all
    await run_guard()
    console.print()
    await run_symbol()
    console.print()
    await run_vector()
