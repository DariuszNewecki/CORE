# src/cli/resources/constitution/query.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from shared.cli_utils import core_command
from will.tools.policy_vectorizer import PolicyVectorizer

from . import app


console = Console()


@app.command("query")
@core_command(dangerous=False, requires_context=True)
# ID: 3e2bdb30-c7c8-42eb-9c50-ceac1c9c73d1
async def query_constitution(
    ctx: typer.Context,
    text: str = typer.Argument(
        ..., help="Natural language question about the constitution."
    ),
) -> None:
    """
    Perform a semantic search for policies and rules using natural language.

    Example: core-admin constitution query "what are the rules for database access?"
    """
    core_context = ctx.obj
    vectorizer = PolicyVectorizer(
        repo_root=core_context.git_service.repo_path,
        cognitive_service=core_context.cognitive_service,
        qdrant_service=core_context.qdrant_service,
    )
    logger.info("[bold cyan]🧠 Searching Mind for:[/bold cyan] '%s'...", text)
    results = await vectorizer.search_policies(query=text, limit=3)
    if not results:
        logger.info("[yellow]No relevant rules found.[/yellow]")
        return
    for i, hit in enumerate(results, 1):
        payload = hit.get("payload", {})
        logger.info(
            "\n[bold green]%s. %s[/bold green] (score: %s)",
            i,
            payload.get("rule_id", "Unknown Rule"),
            hit["score"],
        )
        logger.info("   [dim]%s...[/dim]", payload.get("content", "")[:200])
