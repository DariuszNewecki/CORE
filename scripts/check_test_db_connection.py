# scripts/check_test_db_connection.py
"""
A simple diagnostic script to check the connection to the PostgreSQL test database.
It specifically loads the .env.test file to simulate the pytest environment.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

console = Console()

# Ensure the script can find project modules if needed
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


async def main():
    """Connects to the test DB and reports status."""
    console.print("[bold cyan]--- Test Database Connection Check ---[/bold cyan]")

    # Explicitly load the .env.test file
    env_path = project_root / ".env.test"
    if not env_path.exists():
        console.print(
            f"[bold red]❌ Error: .env.test file not found at {env_path}[/bold red]"
        )
        return 1

    load_dotenv(env_path)
    console.print(f"✅ Loaded configuration from: [green]{env_path}[/green]")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        console.print("[bold red]❌ DATABASE_URL not found in .env.test[/bold red]")
        return 1

    console.print(f"   -> Connecting to: [yellow]{db_url.split('@')[-1]}[/yellow]")

    try:
        engine = create_async_engine(db_url, echo=False, future=True)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version_string = result.scalar_one()

        console.print("\n[bold green]✅ Connection Successful![/bold green]")
        console.print(f"   -> PostgreSQL Version: {version_string.split(',')[0]}")
        return 0

    except Exception as e:
        console.print("\n[bold red]❌ Connection FAILED.[/bold red]")
        console.print(f"   -> Error: {e}")
        console.print("\n[bold yellow]Common Causes:[/bold yellow]")
        console.print("   1. A PostgreSQL Docker container is not running.")
        console.print("   2. The credentials or port in .env.test are incorrect.")
        console.print("   3. A firewall is blocking the connection to port 5432.")
        return 1
    finally:
        if "engine" in locals():
            await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
