# src/cli/commands/develop.py
"""Unified interface for AI-native development.

Thin client over POST /v1/refactor/autonomous (ADR-057 D2). The A3 loop
runs server-side; this CLI dispatches the goal, polls the run resource,
and renders the outcome.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()
develop_app = typer.Typer(
    help="AI-native development with constitutional governance", no_args_is_help=True
)


@develop_app.command("refactor")
@core_command(dangerous=True, requires_context=False)
# ID: 44c3e345-cc9a-4a81-a207-0ea84b69ff37
async def refactor_command(
    ctx: typer.Context,
    goal: str | None = typer.Argument(
        None,
        help="File path or high-level refactoring goal (e.g. 'src/utils.py' or 'Improve modularity of UserService').",
    ),
    from_file: Path | None = typer.Option(
        None, "--from-file", "-f", help="Read the goal from a file."
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually apply changes to the codebase."
    ),
):
    """Initiates an autonomous refactoring cycle via /v1/refactor/autonomous.

    The command intelligently formats goals for INTERPRET phase:
    - If goal looks like a file path: "refactor {path} for better modularity"
    - If goal is natural language: passes as-is
    """
    _ = ctx
    if not goal and (not from_file):
        console.print(
            "[red]❌ You must provide a goal either as an argument or with --from-file.[/red]"
        )
        raise typer.Exit(code=1)

    raw_goal = (
        from_file.read_text(encoding="utf-8").strip()
        if from_file
        else (goal or "").strip()
    )
    goal_content = _format_refactor_goal(raw_goal)
    if goal_content != raw_goal:
        console.print(f"🔍 Formatted goal for INTERPRET phase: {goal_content}")

    console.print(f"🚀 Starting autonomous refactor for: {goal_content}")
    client = CoreApiClient()
    initial = await client.refactor_autonomous(goal=goal_content, write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(
            f"[red]❌ refactor_autonomous failed to dispatch: {initial}[/red]"
        )
        raise typer.Exit(code=1)

    console.print(f"[dim]Dispatched run {run_id} — polling…[/dim]")
    final = await client.poll_refactor_run(run_id)

    result = final.get("result") or {}
    message = result.get("message") or final.get("error") or "(no message)"
    if final.get("status") == "completed" and result.get("success"):
        console.print(f"\n[bold green]✅ Success:[/bold green] {message}")
        proposals = result.get("proposal_ids") or []
        if proposals:
            console.print(
                f"[cyan]Generated {len(proposals)} proposal(s):[/cyan] "
                + ", ".join(proposals[:5])
                + (f" (+{len(proposals) - 5} more)" if len(proposals) > 5 else "")
            )
    else:
        console.print(f"[red]Goal execution failed: {message}[/red]")
        raise typer.Exit(code=1)


def _format_refactor_goal(raw_goal: str) -> str:
    """Format raw goal into INTERPRET-friendly refactoring goal."""
    refactor_keywords = [
        "refactor",
        "modularity",
        "split",
        "extract",
        "improve",
        "clarity",
    ]
    if any(keyword in raw_goal.lower() for keyword in refactor_keywords):
        return raw_goal
    if "/" in raw_goal or raw_goal.endswith(".py"):
        return f"refactor {raw_goal} for better modularity"
    return raw_goal


@develop_app.command("info")
# ID: 7964aa47-e138-4519-bdf3-e788b388e426
def info():
    """Show information about the autonomous development system."""
    body = (
        "[bold cyan]CORE Autonomous Development[/bold cyan]\n\n"
        "This command group uses the A3 (Planning-Specification-Execution) loop\n"
        "to perform complex code modifications autonomously via the API.\n\n"
        'Usage: [yellow]core-admin develop refactor "your goal"[/yellow]\n\n'
        "[bold]Smart Goal Formatting:[/bold]\n"
        "• File paths are auto-formatted with refactoring context\n"
        "• Natural language goals pass through unchanged\n\n"
        "Examples:\n"
        "  core-admin develop refactor src/utils.py --write\n"
        '  core-admin develop refactor "Improve clarity of AuthService" --write'
    )
    console.print(Panel.fit(body, border_style="cyan"))
