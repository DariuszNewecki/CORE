# scripts/demo_graph_context.py
"""
A simple demonstration script to showcase the graph-aware ContextBuilder.
"""

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add project root to path to allow imports from src/
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from services.clients.qdrant_client import QdrantService
from services.context import ContextService
from services.database.session_manager import get_session
from will.orchestration.cognitive_service import CognitiveService


async def run_demonstration():
    """
    Builds a context packet with graph traversal and prints the results.
    """
    console = Console()
    console.print(
        "[bold cyan]--- Graph-Aware ContextBuilder Demonstration ---[/bold cyan]"
    )

    # 1. Define a task that targets a specific function and requests graph traversal.
    # We are targeting `display_error` and asking for related functions (depth=1).
    task_spec = {
        "task_id": "DEMO_GRAPH_001",
        "task_type": "refactor",
        "summary": "Demonstrate graph traversal for the display_error function.",
        "target_file": "src/shared/cli_utils.py",
        "target_symbol": "display_error",
        "scope": {
            "include": ["src/shared/cli_utils.py"],
            "roots": ["src/shared"],
            "traversal_depth": 1,  # <--- THIS ENABLES THE NEW FEATURE
        },
        "constraints": {
            "max_items": 20,
        },
    }
    console.print(
        f"\n[bold]1. Task defined for:[/bold] [green]{task_spec['target_symbol']}[/green] with traversal_depth = 1"
    )

    # 2. Initialize services
    cognitive_service = CognitiveService(repo_path=project_root)
    await cognitive_service.initialize()

    async with get_session() as db_session:
        service = ContextService(
            db_service=db_session,
            qdrant_client=QdrantService(),
            cognitive_service=cognitive_service,
            project_root=str(project_root),
        )

        # 3. Build the context packet.
        console.print(
            "[bold]2. Building context packet...[/bold] (This will query the database)"
        )
        packet = await service.build_for_task(task_spec, use_cache=False)

    # 4. Display the results.
    console.print("\n[bold]3. Context Building Complete. Analyzing results...[/bold]")
    context_items = packet.get("context", [])

    if not context_items:
        console.print("[bold red]Error: No context items were generated.[/bold red]")
        return

    table = Table(title="Symbols Included in the Context Package")
    table.add_column("Symbol Name", style="cyan")
    table.add_column("Source of Inclusion", style="magenta")

    found_target = False
    found_related = False

    for item in context_items:
        source = item.get("source", "unknown")
        if "display_error" in item.get("name", ""):
            found_target = True
            table.add_row(
                item.get("name"), f"[bold green]{source}[/bold green] (Target)"
            )
        elif source == "db_graph_traversal":
            found_related = True
            table.add_row(
                item.get("name"), f"[bold yellow]{source}[/bold yellow] (Related)"
            )
        else:
            table.add_row(item.get("name"), source)

    console.print(table)

    console.print("\n[bold]4. Conclusion:[/bold]")
    if found_target and found_related:
        console.print(
            "[bold green]✅ SUCCESS![/bold green] The context includes the target symbol AND related symbols found by traversing the knowledge graph."
        )
    elif found_target:
        console.print(
            "[bold yellow]⚠️ PARTIAL SUCCESS:[/bold yellow] The context includes the target symbol, but no related symbols were found. Check if the `symbol_calls` table is populated."
        )
    else:
        console.print(
            "[bold red]❌ FAILURE:[/bold red] The context builder did not include the target symbol."
        )


if __name__ == "__main__":
    asyncio.run(run_demonstration())
