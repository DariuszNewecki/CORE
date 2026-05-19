# src/cli/logic/interactive_test/ui.py
"""
Interactive test generation UI utilities.

Handles all Rich console output, user prompts, and display formatting.

Constitutional Compliance:
- Single Responsibility: Only UI presentation logic
- Separation: No business logic, only display and input
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


console = Console()


# ID: 598a5ebc-e0c7-4888-bfe0-e1c5924cbf8b
def prompt_user(
    title: str,
    message: str,
    options: dict[str, str],
    preview: str | None = None,
    artifact_path: Path | None = None,
) -> str:
    """
    Prompt user for input with rich formatting.

    Args:
        title: Step title
        message: Description message
        options: Dict of {key: description}
        preview: Optional code/text preview
        artifact_path: Optional path to full artifact

    Returns:
        User's choice (one of the option keys)
    """
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print(message)
    console.print()
    if preview:
        console.print("[dim]Preview (first 20 lines):[/dim]")
        console.print("─" * 60)
        lines = preview.splitlines()[:20]
        syntax = Syntax("\n".join(lines), "python", theme="monokai", line_numbers=True)
        console.print(syntax)
        if len(preview.splitlines()) > 20:
            console.print(
                f"[dim]... ({len(preview.splitlines()) - 20} more lines)[/dim]"
            )
        console.print("─" * 60)
        console.print("")
    if artifact_path:
        console.print(f"📂 Full output: [cyan]{artifact_path}[/cyan]")
        console.print("")
    console.print("[bold]Options:[/bold]")
    for key, desc in options.items():
        console.print(f"  [bold yellow]\\[{key}\\][/bold yellow] {desc}")
    console.print()
    while True:
        choice = (
            console.input("[bold yellow]Your choice:[/bold yellow] ").strip().lower()
        )
        if choice in options:
            return choice
        console.print(
            f"[red]Invalid choice. Please enter one of: {', '.join(options.keys())}[/red]"
        )


# ID: d0acb2ce-4e85-44d4-9263-5d0f14c70a3f
def show_header(target_file: str) -> None:
    """
    Display workflow header.

    Args:
        target_file: Target file being processed
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]🎯 INTERACTIVE TEST GENERATION[/bold cyan]\nTarget: [yellow]{target_file}[/yellow]",
            border_style="cyan",
        )
    )
    console.print()


# ID: 1a122966-5c44-4889-96b0-f517fa58bbd4
def show_step_header(step_num: int, total_steps: int, title: str) -> None:
    """
    Display step header.

    Args:
        step_num: Current step number
        total_steps: Total number of steps
        title: Step title
    """
    console.print()
    console.print(f"[bold cyan]{title} STEP {step_num}/{total_steps}[/bold cyan]")


# ID: 6699412d-b837-4213-8426-7ea1ecbd1f61
def show_code_preview(code: str, message: str = "Preview (first 20 lines):") -> None:
    """
    Display code preview with syntax highlighting.

    Args:
        code: Code to display
        message: Optional message before preview
    """
    console.print(f"[dim]{message}[/dim]")
    console.print("─" * 60)
    lines = code.splitlines()[:20]
    syntax = Syntax("\n".join(lines), "python", theme="monokai", line_numbers=True)
    console.print(syntax)
    if len(code.splitlines()) > 20:
        console.print(f"[dim]... ({len(code.splitlines()) - 20} more lines)[/dim]")
    console.print("─" * 60)
    console.print()


# ID: 71efbee8-d95e-4fd3-9fe6-d9f172d22ef7
def show_full_code(code: str) -> None:
    """
    Display full code with syntax highlighting.

    Args:
        code: Code to display
    """
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    console.print(syntax)


# ID: ad2cca60-e2cd-4cde-9faf-4a51405decf7
def show_diff(diff_content: str) -> None:
    """
    Display diff with syntax highlighting.

    Args:
        diff_content: Diff content to display
    """
    syntax = Syntax(diff_content, "diff", theme="monokai")
    console.print(syntax)


# ID: c43e9ff7-0ac0-4d30-b8a2-ae6a42811444
def show_success_message(test_path: str) -> None:
    """
    Display success message with next steps.

    Args:
        test_path: Path to created test file
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]🎉 SUCCESS![/bold green]\n\nCreated: [cyan]{test_path}[/cyan]\n\nNext steps:\n  - Run: pytest {test_path}\n  - Review: git diff",
            border_style="green",
        )
    )


# ID: 62c8c780-c666-4eee-a6a9-ba385f60c122
def show_cancellation() -> None:
    """Display cancellation message."""
    console.print("[yellow]❌ Cancelled by user[/yellow]")


# ID: 668baf58-4275-4f61-be7f-07c6aa80fe54
def show_progress(message: str) -> None:
    """
    Display progress message.

    Args:
        message: Progress message to display
    """
    console.print(f"  → {message}")


# ID: 8137e5f6-f250-4921-986d-85dfd8b09e65
def show_success_indicator(message: str) -> None:
    """
    Display success indicator.

    Args:
        message: Success message to display
    """
    console.print(f"    ✅ {message}")


# ID: 3fd75b1e-12a2-4b3e-a001-20212a72191d
def wait_for_continue() -> None:
    """Wait for user to press Enter."""
    console.input("\n[dim]Press Enter to continue...[/dim]")
