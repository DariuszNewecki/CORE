# verify_view.py
import asyncio

from rich.console import Console
from sqlalchemy import text

from src.services.database.session_manager import get_session

console = Console()


async def verify_knowledge_graph_view():
    """
    Connects to the DB and inspects the 'core.knowledge_graph' view
    to confirm if the 'vector_id' column is present and populated.
    """
    console.print("[bold cyan]--- Knowledge Graph View Inspector ---[/bold cyan]")
    try:
        async with get_session() as session:
            console.print("✅ Successfully connected to the database.")

            # Find one symbol that we know has a vector link.
            stmt_find_linked = text(
                "SELECT symbol_id FROM core.symbol_vector_links LIMIT 1"
            )
            result = await session.execute(stmt_find_linked)
            linked_symbol_id = result.scalar_one_or_none()

            if not linked_symbol_id:
                console.print(
                    "[bold yellow]⚠️ No symbols are linked to vectors yet. Run vectorization first.[/bold yellow]"
                )
                return

            console.print(
                f"   -> Found a linked symbol with ID: [dim]{linked_symbol_id}[/dim]"
            )

            # Now, query the VIEW for that specific symbol.
            stmt_check_view = text(
                "SELECT * FROM core.knowledge_graph WHERE uuid = :symbol_id"
            )
            result = await session.execute(
                stmt_check_view, {"symbol_id": linked_symbol_id}
            )
            view_data = result.mappings().first()

            if not view_data:
                console.print(
                    "[bold red]❌ CRITICAL ERROR: The linked symbol was not found in the knowledge_graph view![/bold red]"
                )
                return

            console.print(
                "\n[bold]Inspecting columns from the 'knowledge_graph' view for this symbol:[/bold]"
            )

            # The critical check: is 'vector_id' in the columns?
            if "vector_id" in view_data and view_data["vector_id"] is not None:
                console.print(
                    "[bold green]✅ SUCCESS: The 'vector_id' column is present and populated.[/bold green]"
                )
                console.print(
                    f"   -> vector_id: [green]{view_data['vector_id']}[/green]"
                )
                console.print(
                    "\n[bold yellow]Diagnosis:[/bold yellow] The view is correct. The problem is in the Python code that reads this data."
                )
            else:
                console.print(
                    "[bold red]❌ FAILURE: The 'vector_id' column is MISSING or NULL in the view's output.[/bold red]"
                )
                console.print(
                    f"   -> All columns found: [dim]{list(view_data.keys())}[/dim]"
                )
                console.print(
                    "\n[bold red]Diagnosis:[/bold red] The database view 'core.knowledge_graph' is stale and needs to be updated."
                )

    except Exception as e:
        console.print(f"\n[bold red]❌ An error occurred: {e}[/bold red]")


if __name__ == "__main__":
    asyncio.run(verify_knowledge_graph_view())
