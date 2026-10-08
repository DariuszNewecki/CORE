# src/cli/resources/code/verify.py

"""``core-admin code verify`` — the fast verdict on a change (ADR-168 D4.3).

Producer feedback, not the authoritative audit: it says BLOCKED,
CLEAR_IN_SCOPE, NO_CHANGES or NOT_EVALUATED, names every rule it did not
evaluate, and never says PASS. ``code audit`` (the commit hook, CI) stays authoritative.
Output is the same JSON the MCP tool ``change_verdict`` returns.
"""

from __future__ import annotations

import typer

from cli.utils import core_command
from cli.utils.assistant_output import run_tool
from cli.utils.exit_codes import EXIT_CONFIG_ERROR
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

from .hub import app


@app.command("verify")
@command_meta(
    canonical_name="code.verify",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.USER_FACING,
    summary="Fast verdict on the current change; names what it did not evaluate.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 0a0035af-b49e-4844-95c2-ab238c98b7ba
async def code_verify(
    ctx: typer.Context,
    files: list[str] = typer.Argument(
        None, help="Files to judge. Default: every path that differs from HEAD."
    ),
) -> None:
    """
    Judge the current change against the per-file rules and name every rule
    this run did not evaluate. Exits 1 when the verdict is BLOCKED, 2 when
    nothing could be judged (NOT_EVALUATED).

    Not the authoritative verdict: PASS is given only by `code audit`.

    Example: core-admin code verify
    """
    result = await run_tool("change_verdict", {"files": files} if files else {})
    if result.get("verdict") == "BLOCKED":
        raise typer.Exit(1)
    if result.get("verdict") == "NOT_EVALUATED":
        raise typer.Exit(EXIT_CONFIG_ERROR)
