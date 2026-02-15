# src/body/cli/resources/admin/forensics.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567899

"""
Admin Forensics Command - A2 Chain of Legality Evidence.
Links Agent reasoning to Body execution for constitutional auditing.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from body.cli.logic.governance.forensics_service import GovernanceForensicsService
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("forensics")
@command_meta(
    canonical_name="admin.forensics",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    summary="Investigate the Chain of Legality for a specific session.",
)
@core_command(dangerous=False, requires_context=False)
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567894
async def admin_forensics_cmd(
    session_id: str = typer.Argument(
        ..., help="The UUID of the session to investigate."
    ),
) -> None:
    """
    Reconstructs the history of an autonomous operation.
    Shows exactly what the AI thought vs what the System physically did.
    """
    service = GovernanceForensicsService()

    console.print(
        f"\n[bold cyan]🔎 Forensics: Reconstructing Session {session_id[:8]}...[/bold cyan]\n"
    )

    trail = await service.get_audit_trail(session_id)

    # 1. Show Intent (The Mind)
    if trail["intent"]:
        intent = trail["intent"]
        thought_process = (
            f"[bold]Agent:[/bold] {intent['agent_name']}\n"
            f"[bold]Goal :[/bold] {intent['goal']}\n"
            f"[bold]Patterns Used:[/bold] {intent['pattern_stats']}"
        )
        console.print(
            Panel(
                thought_process,
                title="[blue]Phase A: Intent & Reasoning[/blue]",
                expand=False,
            )
        )
    else:
        console.print("[yellow]⚠️  No decision trace found for this session.[/yellow]")

    # 2. Show Action (The Body)
    if trail["actions"]:
        console.print("\n[blue]Phase B: Executed Actions & Governance Verdicts[/blue]")
        action_table = Table(show_header=True, header_style="bold magenta")
        action_table.add_column("Time", style="dim")
        action_table.add_column("Action", style="cyan")
        action_table.add_column("Result")
        action_table.add_column("Metadata", style="dim")

        for action in trail["actions"]:
            status = (
                "[green]PASS[/green]"
                if action["ok"]
                else f"[red]FAIL: {action['error_message']}[/red]"
            )
            action_table.add_row(
                str(action["created_at"])[:19],
                action["action_type"],
                status,
                str(action["action_metadata"]),
            )
        console.print(action_table)
    else:
        console.print(
            "[yellow]⚠️  No physical actions recorded for this session.[/yellow]"
        )

    # 3. Legality Verdict
    if trail["legality_verified"]:
        console.print(
            "\n[bold green]⚖️  VERDICT: CHAIN OF LEGALITY VERIFIED[/bold green]"
        )
        console.print(
            "[dim]Every action in this session is backed by a recorded reasoning trace.[/dim]\n"
        )
    else:
        console.print(
            "\n[bold red]⚖️  VERDICT: ILLEGITIMATE SESSION DETECTED[/bold red]"
        )
        console.print(
            "[red]Critical Error: This session contains actions that lack recorded intent.[/red]\n"
        )
        raise typer.Exit(code=1)
