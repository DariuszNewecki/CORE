# scripts/check_test_db_connection.py
"""
A diagnostic script to check the connection to the PostgreSQL databases
(core, core_test, core_canary) used by the CORE project.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

console = Console()

# Ensure the script can find project modules if needed
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class DBCheckConfig(NamedTuple):
    """Configuration for a single database check."""

    name: str  # e.g., "Development"
    env_file: str  # e.g., ".env"


def redact_url(url: str) -> str:
    """Removes the password from a database URL for safe printing."""
    if "@" not in url:
        return url
    try:
        parsed = urlparse(url)
        safe_netloc = f"{parsed.username}:********@{parsed.hostname}:{parsed.port}"
        return parsed._replace(netloc=safe_netloc).geturl()
    except Exception:
        return "postgresql+asyncpg://<redacted>"


async def check_connection(db_url: str, db_name: str) -> bool:
    """Connects to a single database and reports its status."""
    console.print(f"   -> Connecting to: [yellow]{redact_url(db_url)}[/yellow]")

    if "$" in db_url:
        console.print(
            "   -> [bold red]Warning:[/bold red] Un-expanded variable (like '$DB_USER') found in URL string. "
            "Ensure your .env file uses explicit values or expansion."
        )

    engine = None
    try:
        engine = create_async_engine(db_url, echo=False, future=True)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version_string = result.scalar_one()

        console.print(
            f"   -> [bold green]✅ Connection Successful![/bold green] (PostgreSQL {version_string.split(',')[0]})"
        )
        return True
    except Exception as e:
        console.print(f"\n[bold red]❌ Connection to '{db_name}' FAILED.[/bold red]")
        console.print(f"   -> [red]Error: {e}[/red]")
        console.print("\n[bold yellow]Common Causes:[/bold yellow]")
        console.print(
            "   1. Your local PostgreSQL service is not running or is not accessible from this machine."
        )
        console.print(
            "   2. The credentials, host, or port in your .env file are incorrect."
        )
        console.print(
            f"   3. The database '{db_name}' does not exist on your PostgreSQL server."
        )
        console.print(
            "   4. A firewall is blocking the connection to the database server."
        )
        return False
    finally:
        if engine:
            await engine.dispose()


async def _async_main(
    dev: bool,
    test: bool,
    canary: bool,
):
    """The core asynchronous logic for the script."""
    console.print(Panel("[bold cyan]CORE Database Connection Check[/bold cyan]"))

    checks_to_run: list[DBCheckConfig] = []
    if dev:
        checks_to_run.append(DBCheckConfig("Development", ".env"))
    if test:
        checks_to_run.append(DBCheckConfig("Test", ".env.test"))
    if canary:
        checks_to_run.append(DBCheckConfig("Canary", ".env.canary"))

    if not checks_to_run:
        console.print("[yellow]No databases selected to check. Exiting.[/yellow]")
        raise typer.Exit()

    results: dict[str, bool] = {}

    for config in checks_to_run:
        console.print(
            f"\n--- Checking [bold]{config.name} DB[/bold] (from {config.env_file}) ---"
        )
        env_path = project_root / config.env_file
        if not env_path.exists():
            console.print(
                f"[bold red]❌ Error: Environment file not found at {env_path}[/bold red]"
            )
            results[config.name] = False
            continue

        load_dotenv(env_path, override=True)

        raw_db_url = os.getenv("DATABASE_URL")
        if not raw_db_url:
            console.print(
                f"[bold red]❌ DATABASE_URL not found in {config.env_file}[/bold red]"
            )
            results[config.name] = False
            continue

        final_db_url = os.path.expandvars(raw_db_url)

        # Extract DB name from the final URL for logging
        db_name_for_log = "unknown"
        try:
            db_name_for_log = urlparse(final_db_url).path.lstrip("/")
        except Exception:
            pass

        results[config.name] = await check_connection(final_db_url, db_name_for_log)

    # --- Final Summary ---
    console.print("\n" + "=" * 40)
    console.print("[bold]Connection Summary[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Environment", style="cyan")
    table.add_column("Status", style="green")

    all_passed = True
    for env_name, passed in results.items():
        status_text = (
            "[green]✅ Connected[/green]" if passed else "[red]❌ FAILED[/red]"
        )
        table.add_row(env_name, status_text)
        if not passed:
            all_passed = False

    console.print(table)
    console.print("=" * 40)

    if not all_passed:
        raise typer.Exit(code=1)


def main(
    dev: bool = typer.Option(True, "--dev/--no-dev", help="Check the Development DB."),
    test: bool = typer.Option(True, "--test/--no-test", help="Check the Test DB."),
    canary: bool = typer.Option(
        True, "--canary/--no-canary", help="Check the Canary DB."
    ),
):
    """Runs connection checks for the specified databases."""
    try:
        asyncio.run(_async_main(dev, test, canary))
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    typer.run(main)
