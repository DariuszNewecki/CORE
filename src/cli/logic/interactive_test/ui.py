# src/body/cli/logic/interactive_test/ui.py

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

from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
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
        console.print()

    if artifact_path:
        console.print(f"📂 Full output: [cyan]{artifact_path}[/cyan]")
        console.print()

    console.print("[bold]Options:[/bold]")
    for key, desc in options.items():
        # Use \\[ and \\] to escape brackets in Rich
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


# ID: 1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e
def show_header(target_file: str) -> None:
    """
    Display workflow header.

    Args:
        target_file: Target file being processed
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]🎯 INTERACTIVE TEST GENERATION[/bold cyan]\n"
            f"Target: [yellow]{target_file}[/yellow]",
            border_style="cyan",
        )
    )
    console.print()


# ID: 2c3d4e5f-6a7b-8c9d-0e1f-2a3b4c5d6e7f
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


# ID: 3d4e5f6a-7b8c-9d0e-1f2a-3b4c5d6e7f8a
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


# ID: 4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b
def show_full_code(code: str) -> None:
    """
    Display full code with syntax highlighting.

    Args:
        code: Code to display
    """
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    console.print(syntax)


# ID: 5f6a7b8c-9d0e-1f2a-3b4c-5d6e7f8a9b0c
def show_diff(diff_content: str) -> None:
    """
    Display diff with syntax highlighting.

    Args:
        diff_content: Diff content to display
    """
    syntax = Syntax(diff_content, "diff", theme="monokai")
    console.print(syntax)


# ID: 6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d
def show_success_message(test_path: str) -> None:
    """
    Display success message with next steps.

    Args:
        test_path: Path to created test file
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]🎉 SUCCESS![/bold green]\n\n"
            f"Created: [cyan]{test_path}[/cyan]\n\n"
            f"Next steps:\n"
            f"  - Run: pytest {test_path}\n"
            f"  - Review: git diff",
            border_style="green",
        )
    )


# ID: 7b8c9d0e-1f2a-3b4c-5d6e-7f8a9b0c1d2e
def show_cancellation() -> None:
    """Display cancellation message."""
    console.print("[yellow]❌ Cancelled by user[/yellow]")


# ID: 8c9d0e1f-2a3b-4c5d-6e7f-8a9b0c1d2e3f
def show_progress(message: str) -> None:
    """
    Display progress message.

    Args:
        message: Progress message to display
    """
    console.print(f"  → {message}")


# ID: 9d0e1f2a-3b4c-5d6e-7f8a-9b0c1d2e3f4a
def show_success_indicator(message: str) -> None:
    """
    Display success indicator.

    Args:
        message: Success message to display
    """
    console.print(f"    ✅ {message}")


# ID: 0e1f2a3b-4c5d-6e7f-8a9b-0c1d2e3f4a5b
def wait_for_continue() -> None:
    """Wait for user to press Enter."""
    console.input("\n[dim]Press Enter to continue...[/dim]")
