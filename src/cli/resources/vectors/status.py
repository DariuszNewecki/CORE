# src/cli/resources/vectors/status.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command

from .hub import app


console = Console()


@app.command("status")
@core_command(dangerous=False, requires_context=True)
# ID: 61334967-75a9-4a0a-96aa-00e53698b7e8
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
        logger.info(table)
    except Exception as e:
        logger.info("[bold red]❌ Qdrant Connection Failed:[/bold red] %s", e)
        raise typer.Exit(1)
