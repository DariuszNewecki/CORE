# src/cli/resources/admin/meta.py
import typer
from rich.console import Console

from body.analyzers.constitutional_path_analyzer import ConstitutionalPathAnalyzer
from cli.utils import core_command
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action

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
# ID: 05ee1736-8480-40f6-94d9-f0e813eb5e0c
async def admin_meta_cmd(
    ctx: typer.Context,
    format: str = typer.Option("list", "--format", help="Output format (list|json)"),
) -> ActionResult:
    """
    Explore the System Mind: Prints all authoritative constitutional files.
    """
    analyzer = ConstitutionalPathAnalyzer()
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
