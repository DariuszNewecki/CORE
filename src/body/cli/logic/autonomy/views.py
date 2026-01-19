# src/body/cli/logic/autonomy/views.py

"""Refactored logic for src/body/cli/logic/autonomy/views.py."""

from __future__ import annotations

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


# ID: 528d48f3-3396-4a3e-80d8-680c0016c4f4
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


# ID: f6e08270-4f85-4a4c-bd3a-ba52fc25d45e
def print_detailed_info(p: Proposal):
    console.print(f"\n[bold cyan]Proposal: {p.proposal_id}[/bold cyan]\n")
    console.print(f"[bold]Goal:[/bold] {p.goal}")
    console.print(f"[bold]Status:[/bold] {p.status.value}")
    console.print(f"[bold]Created:[/bold] {p.created_at}")
    console.print(f"[bold]Created By:[/bold] {p.created_by}\n")

    if p.risk:
        console.print("[bold]Risk Assessment:[/bold]")
        console.print(f"  Overall: {p.risk.overall_risk}")
        console.print(f"  Approval Required: {'Yes' if p.approval_required else 'No'}")
        for factor in p.risk.risk_factors:
            console.print(f"    - {factor}")
        console.print()

    console.print(f"[bold]Actions ({len(p.actions)}):[/bold]")
    for a in sorted(p.actions, key=lambda x: x.order):
        console.print(f"  {a.order + 1}. {a.action_id}")
        if a.parameters:
            console.print(f"     Parameters: {a.parameters}")

    if p.scope.files or p.scope.modules:
        console.print("\n[bold]Scope:[/bold]")
        if p.scope.files:
            console.print(f"  Files: {len(p.scope.files)}")
        if p.scope.modules:
            console.print(f"  Modules: {', '.join(p.scope.modules)}")

    if p.execution_started_at:
        console.print("\n[bold]Execution:[/bold]")
        console.print(f"  Started: {p.execution_started_at}")
        if p.execution_completed_at:
            dur = (p.execution_completed_at - p.execution_started_at).total_seconds()
            console.print(f"  Completed: {p.execution_completed_at}")
            console.print(f"  Duration: {dur:.2f}s")

    if p.failure_reason:
        console.print(f"\n[red]Failure Reason: {p.failure_reason}[/red]")


# ID: 432ef5ef-aec8-43fd-916b-30e145e5a4df
def print_execution_summary(result: dict):
    console.print(f"Actions executed: {result['actions_executed']}")
    console.print(f"Succeeded: {result['actions_succeeded']}")
    console.print(f"Failed: {result['actions_failed']}")
    console.print(f"Duration: {result['duration_sec']:.2f}s\n")

    console.print("[bold]Action Results:[/bold]")
    for action_id, res in result["action_results"].items():
        mark = "[green]✓[/green]" if res["ok"] else "[red]✗[/red]"
        console.print(f"  {mark} {action_id}: {res['duration_sec']:.2f}s")
        if not res["ok"]:
            err = res["data"].get("error", "Unknown error")
            console.print(f"      [red]{err}[/red]")
