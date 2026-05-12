# src/cli/resources/admin/refusals.py

import typer

from cli.utils import core_command
from shared.infrastructure.intent.operational_config import load_operational_config

from .hub import app


_CFG = load_operational_config().misc


@app.command("refusals")
@core_command(dangerous=False, requires_context=False)
# ID: 89bbb5fe-04e4-48b9-9841-3afa714906a2
async def admin_refusals_cmd(
    limit: int = typer.Option(_CFG.refusal_inspect_default_limit, "--limit", "-n"),
    refusal_type: str = typer.Option(
        None, "--type", "-t", help="Filter by type (e.g. boundary, extraction)"
    ),
):
    """
    Audit constitutional refusal outcomes.

    Refusals are first-class outcomes where CORE chose to stop because
    an operation was unsafe or lacked sufficient context.
    """
    from cli.logic.refusal_inspect_logic import show_recent_refusals

    await show_recent_refusals(limit=limit, refusal_type=refusal_type, details=True)
