# src/cli/commands/inspect/drift.py
"""Drift detection commands.

Thin clients over GET /v1/status/drift (ADR-057 D3). The legacy
inspect-side commands stay as deprecated aliases that forward to
`core-admin status drift {scope}`; the `register_guard` helper still
lives in `cli.commands.guard` (the local CLI module, not
`mind.enforcement.guard_cli` — that import was a layer inversion).
"""

from __future__ import annotations

import logging
from collections.abc import Coroutine

import typer

from cli.commands.guard import register_guard
from cli.utils import core_command, deprecated_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta


logger = logging.getLogger(__name__)


def _try_forward_to_status_drift(scope: str, ctx: typer.Context) -> bool:
    """Best-effort forwarder to `core-admin status drift {scope}`.

    Returns False if forwarding unavailable (so the caller can fall back).
    """
    _ = ctx
    try:
        from cli.commands.status import drift_cmd as status_drift_cmd
    except Exception as exc:
        logger.debug("inspect: status drift forward unavailable: %s", exc)
        return False

    try:
        maybe = status_drift_cmd(scope=scope)  # type: ignore[call-arg]
        if isinstance(maybe, Coroutine):
            return False
        return True
    except Exception as exc:
        logger.debug("inspect: status drift forward failed: %s", exc)
        return False


@command_meta(
    canonical_name="inspect.drift.symbol",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Detects drift between filesystem symbols and database symbols",
    aliases=["symbol-drift"],
)
@core_command(dangerous=False, requires_context=False)
# ID: 98134193-955b-4b10-a08c-8d8580e3f3bd
async def symbol_drift_cmd(ctx: typer.Context) -> None:
    """DEPRECATED alias. Use: core-admin status drift symbol."""
    deprecated_command("inspect symbol-drift", "status drift symbol")
    if _try_forward_to_status_drift("symbol", ctx):
        return
    # Fallback to the consolidated drift surface via cli.commands.status.
    from cli.commands.status import drift_cmd as status_drift_cmd

    await status_drift_cmd(ctx, scope="symbol")


@command_meta(
    canonical_name="inspect.drift.vector",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Verifies synchronization between PostgreSQL and Qdrant",
    aliases=["vector-drift"],
)
@core_command(dangerous=False, requires_context=False)
# ID: f08e0006-1485-4118-8e75-f396878faaf5
async def vector_drift_command(ctx: typer.Context) -> None:
    """DEPRECATED alias. Use: core-admin status drift vector."""
    deprecated_command("inspect vector-drift", "status drift vector")
    if _try_forward_to_status_drift("vector", ctx):
        return
    from cli.commands.status import drift_cmd as status_drift_cmd

    await status_drift_cmd(ctx, scope="vector")


drift_commands = [
    {"name": "symbol-drift", "func": symbol_drift_cmd},
    {"name": "vector-drift", "func": vector_drift_command},
]


# ID: 7bc2df06-2d2d-47f4-9c61-3e7045009c5a
def register_drift_commands(app: typer.Typer) -> None:
    """Register drift commands including guard commands.

    Guard commands are registered separately via cli.commands.guard.register_guard
    (a local CLI module, not the mind-side guard_cli helper).
    """
    register_guard(app)
