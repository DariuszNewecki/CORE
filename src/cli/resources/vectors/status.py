# src/body/cli/resources/vectors/status.py
import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("status")
@core_command(dangerous=False, requires_context=True)
# ID: b67cc5bc-9f6b-47c5-94c4-8fead6faa4d1
async def status_vectors(ctx: typer.Context) -> None:
    """Show vector store health and collection statistics."""
    qdrant = ctx.obj.qdrant_service

    try:
        collections = await qdrant.client.get_collections()

        table = Table(title="Qdrant Collections")
        table.add_column("Collection", style="cyan")
        table.add_column("Status", justify="center")

        for coll in collections.collections:
            table.add_row(coll.name, "🟢 Active")

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]❌ Qdrant Connection Failed:[/bold red] {e}")
        raise typer.Exit(1)
