# src/shared/cli_utils/display.py

"""Refactored logic for src/shared/cli_utils/display.py."""

from __future__ import annotations

from rich.console import Console

from shared.action_types import ActionResult


console = Console(log_time=False, log_path=False)


# ID: 7e250730-7fb0-4a75-8baf-5d4d683779d0
def display_error(msg: str) -> None:
    console.print(f"[bold red]{msg}[/bold red]")


# ID: 3eec5993-8d5e-496c-a9f1-5653d7876bcd
def display_success(msg: str) -> None:
    console.print(f"[bold green]{msg}[/bold green]")


# ID: 04387c1f-0d30-44c9-9d40-1496fcd4852d
def display_info(msg: str) -> None:
    console.print(f"[cyan]{msg}[/cyan]")


# ID: a5c10bba-f62e-4b85-ac55-6333480f0b84
def display_warning(msg: str) -> None:
    console.print(f"[yellow]{msg}[/yellow]")


def _display_action_result(result: ActionResult) -> None:
    """Constitutional formatting for ActionResult objects."""
    name = result.action_id or "Command"
    dry_run = (
        result.data.get("dry_run", False) if isinstance(result.data, dict) else False
    )

    if result.ok:
        if isinstance(result.data, dict) and "error" in result.data:
            console.print(
                f"[bold yellow]⚠️  {name} completed with warnings[/bold yellow]"
            )
        elif isinstance(result.data, dict) and "violations_found" in result.data:
            violations = int(result.data["violations_found"])
            if violations == 0:
                console.print(f"[bold green]✅ {name}[/bold green]: All checks passed")
            elif dry_run:
                console.print(
                    f"[yellow]📋 {name}[/yellow]: {violations} violations found (dry-run)"
                )
            else:
                fixed = int(result.data.get("fixed_count", 0))
                console.print(
                    f"[bold green]✅ {name}[/bold green]: Fixed {fixed}/{violations} violations"
                )
        elif isinstance(result.data, dict) and "ids_assigned" in result.data:
            console.print(
                f"[bold green]✅ {name}[/bold green]: {int(result.data['ids_assigned'])} IDs assigned"
            )
        elif isinstance(result.data, dict) and "files_modified" in result.data:
            console.print(
                f"[bold green]✅ {name}[/bold green]: Modified {int(result.data['files_modified'])} files"
            )
        else:
            console.print(f"[bold green]✅ {name}[/bold green]: Completed successfully")
    else:
        error = (
            str(result.data.get("error", "Unknown error"))
            if isinstance(result.data, dict)
            else str(result.data)
        )
        console.print(f"\n[bold red]❌ {name} FAILED[/bold red]")
        console.print(f"   Error: {error}")
        if hasattr(result, "suggestions") and result.suggestions:
            console.print("\n[dim]Suggestions:[/dim]")
            for s in result.suggestions:
                console.print(f"   • {s}")
