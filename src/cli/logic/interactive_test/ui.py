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

from shared.logger import getLogger


logger = getLogger(__name__)
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
    logger.info(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    logger.info(message)
    console.print()
    if preview:
        logger.info("[dim]Preview (first 20 lines):[/dim]")
        logger.info("─" * 60)
        lines = preview.splitlines()[:20]
        syntax = Syntax("\n".join(lines), "python", theme="monokai", line_numbers=True)
        logger.info(syntax)
        if len(preview.splitlines()) > 20:
            logger.info(
                "[dim]... (%s more lines)[/dim]", len(preview.splitlines()) - 20
            )
        logger.info("─" * 60)
        logger.info()
    if artifact_path:
        logger.info("📂 Full output: [cyan]%s[/cyan]", artifact_path)
        logger.info()
    logger.info("[bold]Options:[/bold]")
    for key, desc in options.items():
        logger.info("  [bold yellow]\\[%s\\][/bold yellow] %s", key, desc)
    console.print()
    while True:
        choice = (
            console.input("[bold yellow]Your choice:[/bold yellow] ").strip().lower()
        )
        if choice in options:
            return choice
        logger.info(
            "[red]Invalid choice. Please enter one of: %s[/red]",
            ", ".join(options.keys()),
        )


# ID: d0acb2ce-4e85-44d4-9263-5d0f14c70a3f
def show_header(target_file: str) -> None:
    """
    Display workflow header.

    Args:
        target_file: Target file being processed
    """
    console.print()
    logger.info(
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
    logger.info("[bold cyan]%s STEP %s/%s[/bold cyan]", title, step_num, total_steps)


# ID: 6699412d-b837-4213-8426-7ea1ecbd1f61
def show_code_preview(code: str, message: str = "Preview (first 20 lines):") -> None:
    """
    Display code preview with syntax highlighting.

    Args:
        code: Code to display
        message: Optional message before preview
    """
    logger.info("[dim]%s[/dim]", message)
    logger.info("─" * 60)
    lines = code.splitlines()[:20]
    syntax = Syntax("\n".join(lines), "python", theme="monokai", line_numbers=True)
    logger.info(syntax)
    if len(code.splitlines()) > 20:
        logger.info("[dim]... (%s more lines)[/dim]", len(code.splitlines()) - 20)
    logger.info("─" * 60)
    console.print()


# ID: 71efbee8-d95e-4fd3-9fe6-d9f172d22ef7
def show_full_code(code: str) -> None:
    """
    Display full code with syntax highlighting.

    Args:
        code: Code to display
    """
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    logger.info(syntax)


# ID: ad2cca60-e2cd-4cde-9faf-4a51405decf7
def show_diff(diff_content: str) -> None:
    """
    Display diff with syntax highlighting.

    Args:
        diff_content: Diff content to display
    """
    syntax = Syntax(diff_content, "diff", theme="monokai")
    logger.info(syntax)


# ID: c43e9ff7-0ac0-4d30-b8a2-ae6a42811444
def show_success_message(test_path: str) -> None:
    """
    Display success message with next steps.

    Args:
        test_path: Path to created test file
    """
    console.print()
    logger.info(
        Panel.fit(
            f"[bold green]🎉 SUCCESS![/bold green]\n\nCreated: [cyan]{test_path}[/cyan]\n\nNext steps:\n  - Run: pytest {test_path}\n  - Review: git diff",
            border_style="green",
        )
    )


# ID: 62c8c780-c666-4eee-a6a9-ba385f60c122
def show_cancellation() -> None:
    """Display cancellation message."""
    logger.info("[yellow]❌ Cancelled by user[/yellow]")


# ID: 668baf58-4275-4f61-be7f-07c6aa80fe54
def show_progress(message: str) -> None:
    """
    Display progress message.

    Args:
        message: Progress message to display
    """
    logger.info("  → %s", message)


# ID: 8137e5f6-f250-4921-986d-85dfd8b09e65
def show_success_indicator(message: str) -> None:
    """
    Display success indicator.

    Args:
        message: Success message to display
    """
    logger.info("    ✅ %s", message)


# ID: 3fd75b1e-12a2-4b3e-a001-20212a72191d
def wait_for_continue() -> None:
    """Wait for user to press Enter."""
    console.input("\n[dim]Press Enter to continue...[/dim]")
