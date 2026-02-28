# src/cli/resources/admin/meta.py
# ID: c1b2a3d4-e5f6-7890-abcd-ef1234567813

import typer
from rich.console import Console

from body.analyzers.constitutional_path_analyzer import ConstitutionalPathAnalyzer
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("meta")
@atomic_action(
    action_id="admin.meta",
    intent="List all indexed constitutional files.",
    impact=ActionImpact.READ_ONLY,
    policies=["governance.audit_context"],
)
@core_command(dangerous=False, requires_context=False)
# ID: 99ce89cf-44fa-49ad-bf0c-fa4f0a605d95
async def admin_meta_cmd(
    ctx: typer.Context,
    format: str = typer.Option("list", "--format", help="Output format (list|json)"),
) -> ActionResult:
    """
    Explore the System Mind: Prints all authoritative constitutional files.
    """
    analyzer = ConstitutionalPathAnalyzer()
    # The Body executes the Analyzer; the CLI handles the Rich presentation.
    result = await analyzer.execute()

    paths = result.data["paths"]

    if format == "json":
        import json

        console.print(json.dumps(paths, indent=2))
    else:
        console.print(
            f"\n[bold cyan]🏛️  Authoritative Mind Artifacts ({len(paths)}):[/bold cyan]"
        )
        for p in paths:
            console.print(f"  [dim]•[/dim] {p}")
        console.print()

    return ActionResult(action_id="admin.meta", ok=True, data=result.data)
