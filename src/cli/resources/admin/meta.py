# src/cli/resources/admin/meta.py
from shared.logger import getLogger


logger = getLogger(__name__)
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

        logger.info(json.dumps(paths, indent=2))
    else:
        logger.info(
            "\n[bold cyan]🏛️  Authoritative Mind Artifacts (%s):[/bold cyan]", len(paths)
        )
        for p in paths:
            logger.info("  [dim]•[/dim] %s", p)
        logger.info()
    return ActionResult(action_id="admin.meta", ok=True, data=result.data)
