# src/body/cli/resources/admin/patterns.py
# ID: 8e945fc9-82ae-4ef7-a5fb-f296babaecd7

import typer

from shared.cli_utils import core_command

from .hub import app


@app.command("patterns")
@core_command(dangerous=False, requires_context=True)
# ID: 2763bdbf-a6d8-44f5-bf47-5972d4dee390
async def admin_patterns_cmd(
    ctx: typer.Context,
    last: int = typer.Option(
        10, "--last", "-l", help="Number of recent traces to analyze."
    ),
):
    """
    Analyze architectural pattern usage and classification accuracy.

    Helps identify if certain code patterns (like 'action_pattern')
    are frequently misidentified or failing validation.
    """
    from cli.commands.inspect.patterns import patterns_cmd as logic_func

    # We forward to the existing logic which analyzes JSON traces in reports/
    await logic_func(ctx, last=last)
