# scripts/test_qdrant_connection.py
import asyncio
import sys
from pathlib import Path

# Add the 'src' directory to Python's path to allow imports
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from qdrant_client import AsyncQdrantClient
from rich.console import Console
from shared.config import settings

console = Console()


async def test_qdrant_connection():
    """
    A minimal script to test the connection to Qdrant using the application's
    exact configuration and client library. This isolates the problem.
    """
    console.print("[bold cyan]--- Qdrant Connection Isolation Test ---[/bold cyan]")
    console.print(
        f"   -> Attempting to connect to: [yellow]{settings.QDRANT_URL}[/yellow]"
    )
    console.print(
        f"   -> Using collection: [yellow]{settings.QDRANT_COLLECTION_NAME}[/yellow]"
    )

    try:
        qdrant_client = AsyncQdrantClient(
            url=settings.QDRANT_URL, api_key=settings.model_extra.get("QDRANT_API_KEY")
        )

        # 1. First, get ANY point from the collection to have a valid ID to test with.
        console.print(
            "\n[bold]Step 1: Fetching a single point to get a valid ID...[/bold]"
        )
        scroll_result, _ = await qdrant_client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            limit=1,
            with_payload=False,
            with_vectors=False,
        )

        if not scroll_result:
            console.print(
                "[bold yellow]⚠️ The collection is empty. This is not an error, but the test cannot proceed.[/bold yellow]"
            )
            console.print(
                "   -> Run `bash scripts/reset_and_rebuild_db.sh` to populate the database."
            )
            return

        test_point_id = scroll_result[0].id
        console.print(
            f"   -> Found a valid point to test with. ID: [green]{test_point_id}[/green]"
        )

        # 2. Now, attempt the EXACT operation that is failing in the main app.
        console.print(
            "\n[bold]Step 2: Attempting to retrieve the point by its ID...[/bold]"
        )
        records = await qdrant_client.retrieve(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            ids=[test_point_id],
            with_vectors=True,
        )

        if records:
            console.print(
                "[bold green]✅ SUCCESS: The client successfully retrieved the vector.[/bold green]"
            )
            console.print("   -> This means the connection is working perfectly.")
            console.print(
                "\n[bold red]DIAGNOSIS:[/bold red] The problem is NOT in the client or network, but somewhere inside the main CORE application's complex logic."
            )
        else:
            console.print(
                "[bold red]❌ FAILURE: The client failed to retrieve a known-good point.[/bold red]"
            )

    except Exception as e:
        console.print("\n[bold red]❌ TEST FAILED WITH AN EXCEPTION[/bold red]")
        console.print(f"   -> Exception Type: {type(e).__name__}")
        console.print(f"   -> Error Message: {e}")
        console.print(
            "\n[bold red]DIAGNOSIS:[/bold red] This proves the problem is in the connection between the `qdrant-client` library and your Docker/network setup. The main application code is not the issue."
        )


if __name__ == "__main__":
    asyncio.run(test_qdrant_connection())
