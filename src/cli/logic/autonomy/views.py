# src/cli/logic/autonomy/views.py
"""Refactored logic for src/body/cli/logic/autonomy/views.py."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.table import Table


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
RISK_COLORS = {"safe": "green", "moderate": "yellow", "high": "red"}


# ID: 1d435482-a764-45be-a51d-c5c70eff6c9a
def render_list_table(proposals: list[dict], title: str) -> Table:
    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Goal", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Actions", justify="center")
    table.add_column("Risk", justify="center")
    table.add_column("Created", style="dim")
    for p in proposals:
        status = p["status"]
        s_color = STATUS_COLORS.get(status, "white")
        risk_level = p["risk"]["overall_risk"] if p.get("risk") else "unknown"
        r_color = RISK_COLORS.get(risk_level, "white")
        created = datetime.fromisoformat(p["created_at"]).strftime("%Y-%m-%d %H:%M")
        goal = p.get("goal") or ""
        table.add_row(
            p["proposal_id"][:8] + "...",
            goal[:50] + ("..." if len(goal) > 50 else ""),
            f"[{s_color}]{status}[/{s_color}]",
            str(len(p.get("actions", []))),
            f"[{r_color}]{risk_level}[/{r_color}]",
            created,
        )
    return table


# ID: 94d02f4b-3d3a-4fd5-8332-132eb7980974
def print_detailed_info(p: dict):
    console.print(f"\n[bold cyan]Proposal: {p['proposal_id']}[/bold cyan]\n")
    console.print(f"[bold]Goal:[/bold] {p.get('goal', '')}")
    console.print(f"[bold]Status:[/bold] {p['status']}")
    console.print(f"[bold]Created:[/bold] {p['created_at']}")
    console.print(f"[bold]Created By:[/bold] {p.get('created_by', '')}\n")
    risk = p.get("risk")
    if risk:
        console.print("[bold]Risk Assessment:[/bold]")
        console.print(f"  Overall: {risk['overall_risk']}")
        approval = "Yes" if p.get("approval_required") else "No"
        console.print(f"  Approval Required: {approval}")
        for factor in risk.get("risk_factors", []):
            console.print(f"    - {factor}")
        console.print("")
    actions = p.get("actions", [])
    console.print(f"[bold]Actions ({len(actions)}):[/bold]")
    for a in sorted(actions, key=lambda x: x.get("order", 0)):
        ref = a.get("action_id") or a.get("flow_id") or "?"
        console.print(f"  {a.get('order', 0) + 1}. {ref}")
        if a.get("parameters"):
            console.print(f"     Parameters: {a['parameters']}")
    scope = p.get("scope") or {}
    files = scope.get("files") or []
    modules = scope.get("modules") or []
    if files or modules:
        console.print("\n[bold]Scope:[/bold]")
        if files:
            console.print(f"  Files: {len(files)}")
        if modules:
            console.print(f"  Modules: {', '.join(modules)}")
    started = p.get("execution_started_at")
    completed = p.get("execution_completed_at")
    if started:
        console.print("\n[bold]Execution:[/bold]")
        console.print(f"  Started: {started}")
        if completed:
            dur = (
                datetime.fromisoformat(completed) - datetime.fromisoformat(started)
            ).total_seconds()
            console.print(f"  Completed: {completed}")
            console.print(f"  Duration: {dur}s")
    failure_reason = p.get("failure_reason")
    if failure_reason:
        console.print(f"\n[red]Failure Reason: {failure_reason}[/red]")


# ID: a649ba15-71d8-46ee-b4cd-9888207ed45d
def print_execution_summary(result: dict):
    if not result.get("ok") and "actions_executed" not in result:
        # Early-exit result from executor (proposal not approved, not found, etc.)
        console.print(f"Error: {result.get('error', 'Unknown error')}")
        return
    console.print(f"Actions executed: {result.get('actions_executed', 0)}")
    console.print(f"Succeeded: {result.get('actions_succeeded', 0)}")
    console.print(f"Failed: {result.get('actions_failed', 0)}")
    console.print(f"Duration: {result.get('duration_sec', 0)}s\n")
    console.print("[bold]Action Results:[/bold]")
    for action_id, res in result.get("action_results", {}).items():
        mark = "[green]✓[/green]" if res["ok"] else "[red]✗[/red]"
        console.print(f"  {mark} {action_id}: {res['duration_sec']}s")
        if not res["ok"]:
            err = res.get("data", {}).get("error", "Unknown error")
            console.print(f"      [red]{err}[/red]")
