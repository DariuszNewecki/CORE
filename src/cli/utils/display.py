# src/cli/utils/display.py
"""Refactored logic for src/shared/cli_utils/display.py."""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from rich.console import Console

from shared.action_types import ActionResult


console = Console(log_time=False, log_path=False)


# ID: be1d0b9b-12be-4d5e-8273-35738cb4ae7b
def display_error(msg: str) -> None:
    logger.info("[bold red]%s[/bold red]", msg)


# ID: ab40a3da-7125-4a51-b064-7667a13add79
def display_success(msg: str) -> None:
    logger.info("[bold green]%s[/bold green]", msg)


# ID: ba28b9c3-3a4a-4e9e-9d07-2a83af86600a
def display_info(msg: str) -> None:
    logger.info("[cyan]%s[/cyan]", msg)


# ID: 675459c5-bd1b-4f21-9916-114edb9c2a52
def display_warning(msg: str) -> None:
    logger.info("[yellow]%s[/yellow]", msg)


def _display_action_result(result: ActionResult) -> None:
    """Constitutional formatting for ActionResult objects."""
    name = result.action_id or "Command"
    dry_run = (
        result.data.get("dry_run", False) if isinstance(result.data, dict) else False
    )
    if result.ok:
        if isinstance(result.data, dict) and "error" in result.data:
            logger.info(
                "[bold yellow]⚠️  %s completed with warnings[/bold yellow]", name
            )
        elif isinstance(result.data, dict) and "violations_found" in result.data:
            violations = int(result.data["violations_found"])
            if violations == 0:
                logger.info("[bold green]✅ %s[/bold green]: All checks passed", name)
            elif dry_run:
                logger.info(
                    "[yellow]📋 %s[/yellow]: %s violations found (dry-run)",
                    name,
                    violations,
                )
            else:
                fixed = int(result.data.get("fixed_count", 0))
                logger.info(
                    "[bold green]✅ %s[/bold green]: Fixed %s/%s violations",
                    name,
                    fixed,
                    violations,
                )
        elif isinstance(result.data, dict) and "ids_assigned" in result.data:
            logger.info(
                "[bold green]✅ %s[/bold green]: %s IDs assigned",
                name,
                int(result.data["ids_assigned"]),
            )
        elif isinstance(result.data, dict) and "files_modified" in result.data:
            logger.info(
                "[bold green]✅ %s[/bold green]: Modified %s files",
                name,
                int(result.data["files_modified"]),
            )
        else:
            logger.info("[bold green]✅ %s[/bold green]: Completed successfully", name)
    else:
        error = (
            str(result.data.get("error", "Unknown error"))
            if isinstance(result.data, dict)
            else str(result.data)
        )
        logger.info("\n[bold red]❌ %s FAILED[/bold red]", name)
        logger.info("   Error: %s", error)
        if hasattr(result, "suggestions") and result.suggestions:
            logger.info("\n[dim]Suggestions:[/dim]")
            for s in result.suggestions:
                logger.info("   • %s", s)
