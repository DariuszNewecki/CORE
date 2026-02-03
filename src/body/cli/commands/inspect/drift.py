# src/body/cli/commands/inspect/drift.py
# ID: body.cli.commands.inspect.drift

"""
Drift detection commands.

Commands:
- inspect symbol-drift - Filesystem vs database symbol drift
- inspect vector-drift - PostgreSQL vs Qdrant drift
- Guard commands registered via register_guard()
"""

from __future__ import annotations

from collections.abc import Coroutine

import typer

from body.cli.logic.symbol_drift import inspect_symbol_drift
from body.cli.logic.vector_drift import inspect_vector_drift
from mind.enforcement.guard_cli import register_guard
from shared.cli_utils import core_command, deprecated_command
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


logger = getLogger(__name__)


def _try_forward_to_status_drift(scope: str, ctx: typer.Context) -> bool:
    """
    Best-effort forwarder to the new golden-path command:
      core-admin status drift {guard|symbol|vector|all}

    Returns False if forwarding unavailable (for fallback).
    """
    try:
        from body.cli.commands.status import drift_cmd as status_drift_cmd
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
@core_command(dangerous=False)
# ID: 98134193-955b-4b10-a08c-8d8580e3f3bd
def symbol_drift_cmd(ctx: typer.Context) -> None:
    """
    DEPRECATED alias. Detects drift between filesystem symbols and database symbols.

    Use: core-admin status drift symbol
    """
    deprecated_command("inspect symbol-drift", "status drift symbol")
    if _try_forward_to_status_drift("symbol", ctx):
        return

    # Fallback to current implementation (non-breaking)
    inspect_symbol_drift()


@command_meta(
    canonical_name="inspect.drift.vector",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Verifies synchronization between PostgreSQL and Qdrant",
    aliases=["vector-drift"],
)
@core_command(dangerous=False)
# ID: f08e0006-1485-4118-8e75-f396878faaf5
async def vector_drift_command(ctx: typer.Context) -> None:
    """
    DEPRECATED alias. Verifies synchronization between PostgreSQL and Qdrant.

    Use: core-admin status drift vector
    """
    deprecated_command("inspect vector-drift", "status drift vector")
    if _try_forward_to_status_drift("vector", ctx):
        return

    core_context: CoreContext = ctx.obj
    await inspect_vector_drift(core_context)


# Export commands for registration
drift_commands = [
    {"name": "symbol-drift", "func": symbol_drift_cmd},
    {"name": "vector-drift", "func": vector_drift_command},
]


# ID: 7bc2df06-2d2d-47f4-9c61-3e7045009c5a
def register_drift_commands(app: typer.Typer) -> None:
    """
    Register drift commands including guard commands.

    Note: Guard commands are registered separately via register_guard()
    This function is called from __init__.py after app creation.
    """
    # Register guard commands (drift guard, etc.)
    register_guard(app)
