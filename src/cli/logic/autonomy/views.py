# src/cli/logic/autonomy/views.py
"""Refactored logic for src/body/cli/logic/autonomy/views.py."""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from rich.console import Console
from rich.table import Table

from will.autonomy.proposal import Proposal


console = Console()
STATUS_COLORS = {
    "draft": "white",
    "pending": "yellow",
    "approved": "green",
    "executing": "blue",
    "completed": "green",
    "failed": "red",
    "rejected": "red",
}
RISK_COLORS = {"safe": "green", "moderate": "yellow", "dangerous": "red"}


# ID: 1d435482-a764-45be-a51d-c5c70eff6c9a
def render_list_table(proposals: list[Proposal], title: str) -> Table:
    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Goal", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Actions", justify="center")
    table.add_column("Risk", justify="center")
    table.add_column("Created", style="dim")
    for p in proposals:
        s_color = STATUS_COLORS.get(p.status.value, "white")
        risk_level = p.risk.overall_risk if p.risk else "unknown"
        r_color = RISK_COLORS.get(risk_level, "white")
        table.add_row(
            p.proposal_id[:8] + "...",
            p.goal[:50] + ("..." if len(p.goal) > 50 else ""),
            f"[{s_color}]{p.status.value}[/{s_color}]",
            str(len(p.actions)),
            f"[{r_color}]{risk_level}[/{r_color}]",
            p.created_at.strftime("%Y-%m-%d %H:%M"),
        )
    return table


# ID: 94d02f4b-3d3a-4fd5-8332-132eb7980974
def print_detailed_info(p: Proposal):
    logger.info("\n[bold cyan]Proposal: %s[/bold cyan]\n", p.proposal_id)
    logger.info("[bold]Goal:[/bold] %s", p.goal)
    logger.info("[bold]Status:[/bold] %s", p.status.value)
    logger.info("[bold]Created:[/bold] %s", p.created_at)
    logger.info("[bold]Created By:[/bold] %s\n", p.created_by)
    if p.risk:
        logger.info("[bold]Risk Assessment:[/bold]")
        logger.info("  Overall: %s", p.risk.overall_risk)
        logger.info("  Approval Required: %s", "Yes" if p.approval_required else "No")
        for factor in p.risk.risk_factors:
            logger.info("    - %s", factor)
        logger.info()
    logger.info("[bold]Actions (%s):[/bold]", len(p.actions))
    for a in sorted(p.actions, key=lambda x: x.order):
        logger.info("  %s. %s", a.order + 1, a.action_id)
        if a.parameters:
            logger.info("     Parameters: %s", a.parameters)
    if p.scope.files or p.scope.modules:
        logger.info("\n[bold]Scope:[/bold]")
        if p.scope.files:
            logger.info("  Files: %s", len(p.scope.files))
        if p.scope.modules:
            logger.info("  Modules: %s", ", ".join(p.scope.modules))
    if p.execution_started_at:
        logger.info("\n[bold]Execution:[/bold]")
        logger.info("  Started: %s", p.execution_started_at)
        if p.execution_completed_at:
            dur = (p.execution_completed_at - p.execution_started_at).total_seconds()
            logger.info("  Completed: %s", p.execution_completed_at)
            logger.info("  Duration: %ss", dur)
    if p.failure_reason:
        logger.info("\n[red]Failure Reason: %s[/red]", p.failure_reason)


# ID: a649ba15-71d8-46ee-b4cd-9888207ed45d
def print_execution_summary(result: dict):
    if not result.get("ok") and "actions_executed" not in result:
        # Early-exit result from executor (proposal not approved, not found, etc.)
        logger.info("Error: %s", result.get("error", "Unknown error"))
        return
    logger.info("Actions executed: %s", result.get("actions_executed", 0))
    logger.info("Succeeded: %s", result.get("actions_succeeded", 0))
    logger.info("Failed: %s", result.get("actions_failed", 0))
    logger.info("Duration: %ss\n", result.get("duration_sec", 0))
    logger.info("[bold]Action Results:[/bold]")
    for action_id, res in result.get("action_results", {}).items():
        mark = "[green]✓[/green]" if res["ok"] else "[red]✗[/red]"
        logger.info("  %s %s: %ss", mark, action_id, res["duration_sec"])
        if not res["ok"]:
            err = res.get("data", {}).get("error", "Unknown error")
            logger.info("      [red]%s[/red]", err)
