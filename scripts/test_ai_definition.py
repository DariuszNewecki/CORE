# scripts/test_ai_definition.py
import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console

# Add src to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.cognitive_service import CognitiveService
from shared.config import settings

console = Console()

# A real, unassigned symbol from your project
HARDCODED_SOURCE_CODE = """
async def run_ssot_migration(dry_run: bool):
    \"\"\"Orchestrates the full one-time migration from files to the SSOT database.\"\"\"
    console.print(
        "🚀 Starting one-time migration of knowledge from files to database..."
    )

    capabilities = await _migrate_capabilities_from_manifest()
    symbols = await _migrate_symbols_from_ast()

    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: The following actions would be taken --[/bold yellow]"
        )
        console.print(
            f"  - Insert {len(capabilities)} unique capabilities from project_manifest.yaml."
        )
        console.print(f"  - Insert {len(symbols)} symbols from source code scan.")
        return

    async with get_session() as session:
        async with session.begin():
            console.print("  -> Deleting existing data from tables...")
            await session.execute(text("DELETE FROM core.symbol_capability_links;"))
            await session.execute(text("DELETE FROM core.symbols;"))
            await session.execute(text("DELETE FROM core.capabilities;"))

            console.print(f"  -> Inserting {len(capabilities)} capabilities...")
            if capabilities:
                await session.execute(
                    text(
                        \"\"\"
                    INSERT INTO core.capabilities (id, name, title, objective, owner, domain, tags, status)
                    VALUES (:id, :name, :title, :objective, :owner, :domain, :tags, :status)
                \"\"\"
                    ),
                    capabilities,
                )

            console.print(f"  -> Inserting {len(symbols)} symbols...")
            if symbols:
                insert_stmt = text(
                    \"\"\"
                    INSERT INTO core.symbols (id, uuid, module, qualname, kind, ast_signature, fingerprint, state, symbol_path)
                    VALUES (:id, :uuid, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :symbol_path)
                    ON CONFLICT (symbol_path) DO NOTHING;
                \"\"\"
                )
                for symbol in symbols:
                    await session.execute(insert_stmt, symbol)

    console.print("[bold green]✅ One-time migration complete.[/bold green]")
    console.print(
        "Run 'core-admin mind snapshot' to create the first export from the database."
    )
"""

async def test_single_definition():
    console.print("[bold cyan]Running isolated AI definition test...[/bold cyan]")

    if not os.getenv("DEEPSEEK_CODER_API_URL"):
        console.print("[bold red]ERROR: DEEPSEEK_CODER_API_URL is not set in your .env file.[/bold red]")
        return

    try:
        cognitive_service = CognitiveService(settings.REPO_PATH)
        await cognitive_service.initialize()
        definer_agent = cognitive_service.get_client_for_role("CodeReviewer")

        prompt_template = (
            "Analyze the following Python code and propose a single, canonical, "
            "dot-notation capability key that follows a `domain.subdomain.action` pattern. "
            "The final part MUST be a verb.\n\n"
            "```python\n{code}\n```\n\n"
            "Respond with ONLY the key and nothing else."
        )
        final_prompt = prompt_template.format(code=HARDCODED_SOURCE_CODE)

        console.print("   -> Sending request to AI...")
        raw_response = definer_agent.make_request_sync(final_prompt, user_id="test_agent")

        console.print("\n--- [bold green]SUCCESS: AI Responded[/bold green] ---")
        console.print(f"Raw Response: [yellow]{raw_response.strip()}[/yellow]")

    except Exception as e:
        console.print("\n--- [bold red]FAILURE: AI Request Failed[/bold red] ---")
        console.print(f"The program crashed with the following error:")
        console.print_exception(show_locals=True)

if __name__ == "__main__":
    asyncio.run(test_single_definition())