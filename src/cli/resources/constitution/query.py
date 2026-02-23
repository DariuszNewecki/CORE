# src/body/cli/resources/constitution/query.py
import typer
from rich.console import Console

from shared.cli_utils import core_command
from will.tools.policy_vectorizer import PolicyVectorizer

from . import app


console = Console()


@app.command("query")
@core_command(dangerous=False, requires_context=True)
# ID: f72fde5c-3890-40e9-a607-a6425eb0add5
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

    # Initialize the vector search tool
    vectorizer = PolicyVectorizer(
        repo_root=core_context.git_service.repo_path,
        cognitive_service=core_context.cognitive_service,
        qdrant_service=core_context.qdrant_service,
    )

    console.print(f"[bold cyan]🧠 Searching Mind for:[/bold cyan] '{text}'...")
    results = await vectorizer.search_policies(query=text, limit=3)

    if not results:
        console.print("[yellow]No relevant rules found.[/yellow]")
        return

    for i, hit in enumerate(results, 1):
        payload = hit.get("payload", {})
        console.print(
            f"\n[bold green]{i}. {payload.get('rule_id', 'Unknown Rule')}[/bold green] (score: {hit['score']:.2f})"
        )
        console.print(f"   [dim]{payload.get('content', '')[:200]}...[/dim]")
