# src/cli/resources/dev/campaign_review.py

"""
Per-cluster review surface for StrategicAuditor campaigns.

`core-admin dev campaign list|accept|reject|execute` lets the governor review
the autonomous clusters a strategic-audit produced and accept them one at a
time. Only accepted clusters execute (ADR-110 D4 — self-extension is a
Governor-role capability; the governor's per-cluster acceptance is the gate,
replacing the old blanket --execute).

LAYER: cli — operator surface driving Will. Runs in-process today; migrating
this to a governor-tier API endpoint is deferred (#670/#671) per ADR-110 D6.
"""

from __future__ import annotations

from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.task_repository import TaskRepository

from .hub import app as dev_app


console = Console()

campaign_app = typer.Typer(
    name="campaign",
    help="Review and execute StrategicAuditor campaign clusters (per-cluster governor review).",
    no_args_is_help=True,
)
dev_app.add_typer(campaign_app, name="campaign")


def _parse_uuid(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as exc:
        console.print(f"[red]❌ Invalid {label}: {raw!r} is not a UUID.[/red]")
        raise typer.Exit(code=1) from exc


def _review_state(task) -> str:
    """Human-readable review state derived from (role, status, requires_approval).

    Approval rides on requires_approval (its purpose); status stays within
    core.tasks' closed lifecycle vocab. See effects.persist_campaign.
    """
    if task.assigned_role == "Human":
        return "escalation"
    if task.status == "blocked":
        return "rejected"
    if task.status == "pending":
        return "awaiting review" if task.requires_approval else "approved"
    return task.status  # executing / completed / failed


@campaign_app.command("list")
@command_meta(
    canonical_name="dev.campaign.list",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.USER_FACING,
    summary="List a campaign's clusters and their review status.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 3f5b9e21-7c84-4d0a-9e6f-1b2c3d4e5f60
async def list_clusters(
    parent_task_id: str = typer.Argument(
        ..., help="Campaign parent Task id (printed by strategic-audit --write)."
    ),
) -> None:
    """Show every cluster of a campaign with its id, status, and confidence."""
    parent = _parse_uuid(parent_task_id, "parent_task_id")
    async with get_session() as session:
        repo = TaskRepository(session)
        children = await repo.list_children(parent)
    if not children:
        console.print(
            f"[yellow]No clusters found for campaign parent {parent_task_id}.[/yellow]"
        )
        return

    table = Table(title=f"Campaign {parent_task_id} — clusters")
    table.add_column("cluster task id", style="cyan", no_wrap=True)
    table.add_column("review state")
    table.add_column("conf", justify="right")
    table.add_column("root cause")
    for c in children:
        ctx_data = c.context or {}
        conf = ctx_data.get("confidence")
        table.add_row(
            str(c.id),
            _review_state(c),
            f"{conf:.2f}" if isinstance(conf, (int, float)) else "—",
            str(ctx_data.get("root_cause", c.intent))[:80],
        )
    console.print(table)
    console.print(
        "\n[dim]Accept a cluster: dev campaign accept <cluster task id> · "
        "then run: dev campaign execute <campaign parent id>[/dim]"
    )


@campaign_app.command("accept")
@command_meta(
    canonical_name="dev.campaign.accept",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Accept one autonomous cluster for execution.",
)
@core_command(dangerous=False, requires_context=False)
# ID: a1c2e3f4-5b60-4789-9a0b-1c2d3e4f5061
async def accept_cluster(
    cluster_task_id: str = typer.Argument(..., help="Cluster Task id to accept."),
) -> None:
    """Move an autonomous cluster to 'approved' so it runs on the next execute."""
    cluster = _parse_uuid(cluster_task_id, "cluster_task_id")
    async with get_session() as session:
        repo = TaskRepository(session)
        task = await repo.get_by_id(cluster)
        if task is None:
            console.print(f"[red]❌ No cluster Task {cluster_task_id}.[/red]")
            raise typer.Exit(code=1)
        if task.assigned_role != "AutonomousDeveloper":
            console.print(
                "[red]❌ Only autonomous clusters can be accepted. "
                "Escalations require a .intent/ amendment, not acceptance.[/red]"
            )
            raise typer.Exit(code=1)
        if not (task.status == "pending" and task.requires_approval):
            console.print(
                f"[yellow]Cluster is '{_review_state(task)}', not awaiting review — no change.[/yellow]"
            )
            raise typer.Exit(code=1)
        await repo.set_approval(cluster, False)
    console.print(
        f"[green]✅ Cluster {cluster_task_id} approved (ready to execute).[/green]"
    )


@campaign_app.command("reject")
@command_meta(
    canonical_name="dev.campaign.reject",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Reject one cluster, recording the reason.",
)
@core_command(dangerous=False, requires_context=False)
# ID: b2d3f405-6c71-4890-ab1c-2d3e4f506172
async def reject_cluster(
    cluster_task_id: str = typer.Argument(..., help="Cluster Task id to reject."),
    reason: str = typer.Option("", "--reason", help="Why the cluster is rejected."),
) -> None:
    """Move a cluster to 'rejected'; it will not execute. Reason stored in context."""
    cluster = _parse_uuid(cluster_task_id, "cluster_task_id")
    async with get_session() as session:
        repo = TaskRepository(session)
        task = await repo.get_by_id(cluster)
        if task is None:
            console.print(f"[red]❌ No cluster Task {cluster_task_id}.[/red]")
            raise typer.Exit(code=1)
        task.status = "blocked"
        new_context = dict(task.context or {})
        new_context["rejection_reason"] = reason
        task.context = new_context
        await session.commit()
    console.print(f"[green]✅ Cluster {cluster_task_id} rejected (blocked).[/green]")


@campaign_app.command("execute")
@command_meta(
    canonical_name="dev.campaign.execute",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.GOVERNOR_ONLY,
    summary="Execute a campaign's approved clusters.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: c3e4f506-7d82-49a1-bc2d-3e4f50617283
async def execute_campaign(
    ctx: typer.Context,
    parent_task_id: str = typer.Argument(..., help="Campaign parent Task id."),
) -> None:
    """Run only the clusters the governor has accepted (status='approved')."""
    from will.agents.strategic_auditor.effects import execute_approved_clusters

    parent = _parse_uuid(parent_task_id, "parent_task_id")
    context: CoreContext = ctx.obj
    async with get_session() as session:
        results = await execute_approved_clusters(context, session, parent)

    if not results:
        console.print(
            "[yellow]No approved clusters to execute.[/yellow] "
            "[dim]Accept clusters first: dev campaign accept <cluster task id>[/dim]"
        )
        return

    ok = sum(1 for _, success, _ in results if success)
    console.print(
        f"\n[bold]Executed {len(results)} approved cluster(s): "
        f"{ok} ok, {len(results) - ok} failed.[/bold]"
    )
    for task_id, success, message in results:
        mark = "[green]OK[/green]" if success else "[red]FAIL[/red]"
        console.print(f"  {mark} {task_id} — {message}")
