# src/cli/resources/law/commands.py

"""``core-admin law show`` / ``law check`` — law answers with provenance (ADR-168 D4.3).

Read-only and service-free: no database, no LLM. Output is the same JSON the
MCP tools ``law_rule`` and ``law_can_write`` return.
"""

from __future__ import annotations

import typer

from cli.utils import core_command
from cli.utils.assistant_output import run_tool
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

from .hub import app


@app.command("show")
@command_meta(
    canonical_name="law.show",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.USER_FACING,
    summary="What a rule says, how it is enforced, and where it is declared.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: ddd73f72-cb26-42d7-ab46-a88165c142c9
async def law_show(
    ctx: typer.Context,
    rule_id: str = typer.Argument(
        ..., help="Rule id, e.g. governance.constitution.read_only."
    ),
) -> None:
    """
    Show what a rule says: statement, enforcement, authority, and the mechanism
    that enforces it, with source files. An undeclared rule is answered as unknown.

    Example: core-admin law show governance.constitution.read_only
    """
    await run_tool("law_rule", {"rule_id": rule_id})


@app.command("check")
@command_meta(
    canonical_name="law.check",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.USER_FACING,
    summary="May a producer write this path? The law, and what enforces it.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 93ac9978-b271-4e94-9099-ee1634a09a68
async def law_check(
    ctx: typer.Context,
    path: str = typer.Argument(
        ..., help="Path to ask about, repo-relative or absolute."
    ),
) -> None:
    """
    Check whether a producer may write PATH. The answer has two parts that are
    never collapsed: what the law says, and what actually enforces it (CORE's
    own write path, and an external assistant editing files directly).

    Example: core-admin law check .intent/rules/architecture/governance_basics.json
    """
    await run_tool("law_can_write", {"path": path})
