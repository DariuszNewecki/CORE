# src/body/cli/commands/inspect.py
"""
Registers the verb-based 'inspect' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
Compliance:
- body_contracts.yaml: UI allowed here (CLI Command Layer).
- command_patterns.yaml: Inspect Pattern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.tree import Tree

import body.cli.logic.status as status_logic

# NEW: Import the pure logic module
from body.cli.logic import diagnostics as diagnostics_logic
from body.cli.logic.duplicates import inspect_duplicates_async
from body.cli.logic.knowledge import find_common_knowledge
from body.cli.logic.symbol_drift import inspect_symbol_drift
from body.cli.logic.vector_drift import inspect_vector_drift
from features.self_healing.test_target_analyzer import TestTargetAnalyzer
from mind.enforcement.guard_cli import register_guard
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()
inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)


@inspect_app.command("status")
@core_command(dangerous=False, requires_context=False)
# ID: fc253528-91bc-44bb-ae52-0ba3886d95d5
async def status_command(ctx: typer.Context) -> None:
    """
    Display database connection and migration status.
    """
    # Delegate to logic layer
    report = await status_logic._get_status_report()

    # Connection line
    if report.is_connected:
        console.print("Database connection: OK")
    else:
        console.print("Database connection: FAILED")

    # Version line
    if report.db_version:
        console.print(f"Database version: {report.db_version}")
    else:
        console.print("Database version: none")

    # Migration status
    pending = list(report.pending_migrations)
    if not pending:
        console.print("Migrations are up to date.")
    else:
        console.print(f"Found {len(pending)} pending migrations")
        for mig in sorted(pending):
            console.print(f"- {mig}")


# Register guard commands (e.g. 'guard drift')
register_guard(inspect_app)


@inspect_app.command("command-tree")
@core_command(dangerous=False, requires_context=False)
# ID: db3b96cc-d4a8-4bb1-9002-5a9b81d96d51
def command_tree_cmd(ctx: typer.Context) -> None:
    """Displays a hierarchical tree view of all available CLI commands."""
    # 1. Get Data (Headless)
    from body.cli.admin_cli import app as main_app

    logger.info("Building CLI Command Tree...")
    tree_data = diagnostics_logic.build_cli_tree_data(main_app)

    # 2. Render UI (Interface Layer)
    root = Tree("[bold blue]CORE CLI[/bold blue]")

    # ID: 33464692-0311-47b5-b972-a26923f152df
    def add_nodes(nodes: list[dict[str, Any]], parent: Tree):
        for node in nodes:
            label = f"[bold]{node['name']}[/bold]"
            if node.get("help"):
                label += f": [dim]{node['help']}[/dim]"

            branch = parent.add(label)
            if "children" in node:
                add_nodes(node["children"], branch)

    add_nodes(tree_data, root)
    console.print(root)


@inspect_app.command("find-clusters")
@core_command(dangerous=False)
# ID: b3272cb8-f754-4a11-b18d-6ca5efecbd3d
async def find_clusters_cmd(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
) -> None:
    """
    Finds and displays all semantic capability clusters.
    """
    # 1. Get Data (Headless)
    core_context: CoreContext = ctx.obj
    clusters = await diagnostics_logic.find_clusters_logic(core_context, n_clusters)

    # 2. Render UI (Interface Layer)
    if not clusters:
        console.print("[yellow]No clusters found.[/yellow]")
        return

    console.print(f"[green]Found {len(clusters)} clusters:[/green]")
    for cluster in clusters:
        console.print(
            f"- {cluster.get('topic', 'Unknown')}: {cluster.get('size', 0)} items"
        )


@inspect_app.command("symbol-drift")
@core_command(dangerous=False)
# ID: c08c957a-f5b3-480d-8232-8c8cafe060d5
def symbol_drift_cmd(ctx: typer.Context) -> None:
    """
    Detects drift between symbols on the filesystem and in the database.
    """
    # inspect_symbol_drift handles its own sync/async logic internally
    inspect_symbol_drift()


@inspect_app.command("vector-drift")
@core_command(dangerous=False)
# ID: 79b5e56e-3aa5-4ce0-a693-e051e0fe1dad
async def vector_drift_command(ctx: typer.Context) -> None:
    """
    Verifies perfect synchronization between PostgreSQL and Qdrant.
    """
    core_context: CoreContext = ctx.obj
    # Framework ensures Qdrant is initialized via JIT
    await inspect_vector_drift(core_context)


@inspect_app.command("common-knowledge")
@core_command(dangerous=False)
# ID: bf926e9a-3106-4697-8d96-ade3fb3cad22
async def common_knowledge_cmd(ctx: typer.Context) -> None:
    """
    Finds structurally identical helper functions that can be consolidated.
    """
    await find_common_knowledge()


@inspect_app.command("decisions")
@core_command(dangerous=False, requires_context=False)
# ID: 8e9f0a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b
async def decisions_cmd(
    ctx: typer.Context,
    recent: int = typer.Option(
        10, "--recent", "-n", help="Number of recent traces to show"
    ),
    session_id: str | None = typer.Option(
        None, "--session", "-s", help="Show specific session by ID"
    ),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Filter by agent name"
    ),
    pattern: str | None = typer.Option(
        None, "--pattern", "-p", help="Filter by pattern used"
    ),
    failures_only: bool = typer.Option(
        False, "--failures-only", "-f", help="Show only traces with violations"
    ),
    stats: bool = typer.Option(
        False, "--stats", help="Show statistics instead of traces"
    ),
    details: bool = typer.Option(
        False, "--details", "-d", help="Show full decision details"
    ),
) -> None:
    """
    Inspect decision traces from autonomous operations.

    Examples:
        core-admin inspect decisions                           # Recent traces
        core-admin inspect decisions --session abc123          # Specific session
        core-admin inspect decisions --failures-only           # Failures only
        core-admin inspect decisions --agent CodeGenerator     # By agent
        core-admin inspect decisions --pattern action_pattern --stats  # Pattern stats
    """
    # requires_context=False: use DB session manager directly
    from shared.infrastructure.database.session_manager import get_session

    async with get_session() as session:
        repo = DecisionTraceRepository(session)

        # Route to appropriate handler
        if session_id:
            await _show_session_trace(repo, session_id, details)
        elif stats:
            await _show_statistics(repo, pattern, days=recent)
        elif pattern:
            await _show_pattern_traces(repo, pattern, recent, details)
        else:
            await _show_recent_traces(repo, recent, agent, failures_only, details)


@inspect_app.command("test-targets")
@core_command(dangerous=False, requires_context=False)
# ID: fc375cbc-c97f-40b5-a4a9-0fa4a4d7d359
def inspect_test_targets(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="The path to the Python file to analyze.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """
    Identifies and classifies functions in a file as SIMPLE or COMPLEX test targets.
    """
    analyzer = TestTargetAnalyzer()
    targets = analyzer.analyze_file(file_path)

    if not targets:
        console.print("[yellow]No suitable public functions found to analyze.[/yellow]")
        return

    from rich.table import Table

    table = Table(
        title="Test Target Analysis", header_style="bold magenta", show_header=True
    )
    table.add_column("Function", style="cyan")
    table.add_column("Complexity", style="magenta", justify="right")
    table.add_column("Classification", style="yellow")
    table.add_column("Reason")

    for target in targets:
        style = "green" if target.classification == "SIMPLE" else "red"
        table.add_row(
            target.name,
            str(target.complexity),
            f"[{style}]{target.classification}[/{style}]",
            target.reason,
        )
    console.print(table)


@inspect_app.command("duplicates")
@core_command(dangerous=False)
# ID: 5a340604-58ea-46d2-8841-a308abad5dff
async def duplicates_command(
    ctx: typer.Context,
    threshold: float = typer.Option(
        0.80,
        "--threshold",
        "-t",
        help="The minimum similarity score to consider a duplicate.",
        min=0.5,
        max=1.0,
    ),
) -> None:
    """
    Runs only the semantic code duplication check.
    """
    core_context: CoreContext = ctx.obj
    await inspect_duplicates_async(context=core_context, threshold=threshold)


# --------------------------------------------------------------------------------------
# Helper functions (must be at end of file)
# --------------------------------------------------------------------------------------


def _as_bool(value: Any) -> bool:
    """
    Normalize repository return types (bool/str/int/None) into a boolean.
    Supports common representations like True/"true"/"1"/1.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "t"}
    return bool(value)


async def _show_session_trace(
    repo: DecisionTraceRepository, session_id: str, details: bool
) -> None:
    """Show a specific session trace."""
    trace = await repo.get_by_session_id(session_id)

    if not trace:
        console.print(f"[yellow]No trace found for session: {session_id}[/yellow]")
        return

    console.print(f"\n[bold cyan]Session: {trace.session_id}[/bold cyan]")
    console.print(f"Agent: {trace.agent_name}")
    console.print(f"Goal: {trace.goal or 'none'}")
    console.print(f"Decisions: {trace.decision_count}")
    console.print(f"Created: {trace.created_at}")

    if _as_bool(getattr(trace, "has_violations", False)):
        console.print(f"[red]Violations: {trace.violation_count}[/red]")

    if details:
        console.print("\n[bold]Decisions:[/bold]")
        for i, decision in enumerate(trace.decisions or [], 1):
            agent = decision.get("agent", "none")
            d_type = decision.get("decision_type", "none")
            console.print(f"\n[cyan]{i}. {agent} - {d_type}[/cyan]")
            console.print(f"  Rationale: {decision.get('rationale', 'none')}")
            console.print(f"  Chosen: {decision.get('chosen_action', 'none')}")

            confidence = decision.get("confidence")
            if isinstance(confidence, (int, float)):
                console.print(f"  Confidence: {confidence:.0%}")
            else:
                console.print("  Confidence: none")


async def _show_recent_traces(
    repo: DecisionTraceRepository,
    limit: int,
    agent: str | None,
    failures_only: bool,
    details: bool,
) -> None:
    """Show recent traces with optional filtering."""
    from rich.table import Table

    traces = await repo.get_recent(
        limit=limit,
        agent_name=agent,
        failures_only=failures_only,
    )

    if not traces:
        console.print("[yellow]No traces found matching criteria[/yellow]")
        return

    table = Table(title=f"Recent Decision Traces ({len(traces)})")
    table.add_column("Session", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Decisions", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Status")
    table.add_column("Created", style="dim")

    for trace in traces:
        duration_ms = getattr(trace, "duration_ms", None)
        duration = (
            f"{duration_ms/1000:.1f}s"
            if isinstance(duration_ms, (int, float))
            else "none"
        )

        has_violations = _as_bool(getattr(trace, "has_violations", False))
        status = "❌ Violations" if has_violations else "✅ Clean"

        created_at = getattr(trace, "created_at", None)
        created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "none"

        table.add_row(
            (trace.session_id or "")[:12],
            trace.agent_name or "none",
            str(getattr(trace, "decision_count", 0)),
            duration,
            status,
            created_str,
        )

    console.print(table)

    if details and traces:
        console.print("\n[dim]Showing details for most recent trace...[/dim]")
        await _show_session_trace(repo, traces[0].session_id, True)


async def _show_pattern_traces(
    repo: DecisionTraceRepository,
    pattern: str,
    limit: int,
    details: bool,
) -> None:
    """Show traces that used a specific pattern."""
    from rich.table import Table

    # NOTE: repository method name is assumed from your pasted implementation.
    traces = await repo.get_pattern_stats(pattern, limit)

    if not traces:
        console.print(f"[yellow]No traces found using pattern: {pattern}[/yellow]")
        return

    console.print(f"\n[bold cyan]Traces using pattern: {pattern}[/bold cyan]")
    console.print(f"Found: {len(traces)} traces\n")

    violations = sum(1 for t in traces if _as_bool(getattr(t, "has_violations", False)))
    success_rate = (len(traces) - violations) / len(traces) * 100 if traces else 0

    console.print(f"Success rate: [green]{success_rate:.1f}%[/green]")
    console.print(f"Violations: [red]{violations}[/red] / {len(traces)}\n")

    if not details:
        table = Table()
        table.add_column("Session", style="cyan")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Created", style="dim")

        for trace in traces[:20]:  # Show max 20 in table
            status = "❌" if _as_bool(getattr(trace, "has_violations", False)) else "✅"
            created_at = getattr(trace, "created_at", None)
            created_str = (
                created_at.strftime("%Y-%m-%d %H:%M") if created_at else "none"
            )
            table.add_row(
                (trace.session_id or "")[:12],
                trace.agent_name or "none",
                status,
                created_str,
            )

        console.print(table)


async def _show_statistics(
    repo: DecisionTraceRepository,
    pattern: str | None,
    days: int = 7,
) -> None:
    """Show decision trace statistics."""
    from rich.table import Table

    console.print(
        f"\n[bold cyan]Decision Trace Statistics (Last {days} days)[/bold cyan]\n"
    )

    # Get agent counts
    agent_counts = await repo.count_by_agent(days)

    if not agent_counts:
        console.print("[yellow]No traces found in the specified time range[/yellow]")
        return

    table = Table(title="Traces by Agent")
    table.add_column("Agent", style="cyan")
    table.add_column("Count", justify="right")

    for agent_name, count in sorted(
        agent_counts.items(), key=lambda x: x[1], reverse=True
    ):
        table.add_row(agent_name, str(count))

    console.print(table)

    if pattern:
        # Show pattern-specific stats
        traces = await repo.get_pattern_stats(pattern, 1000)

        if traces:
            console.print(f"\n[bold]Pattern: {pattern}[/bold]")
            violations = sum(
                1 for t in traces if _as_bool(getattr(t, "has_violations", False))
            )
            success_rate = (
                (len(traces) - violations) / len(traces) * 100 if traces else 0
            )

            console.print(f"Total uses: {len(traces)}")
            console.print(f"Success rate: [green]{success_rate:.1f}%[/green]")
            console.print(f"Violations: [red]{violations}[/red]")
        else:
            console.print(f"\n[yellow]No traces found for pattern: {pattern}[/yellow]")
