# src/cli/commands/inspect/patterns.py
"""
Pattern classification analysis commands.

Commands:
- inspect patterns - Analyze pattern violations and classifications
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import json

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


console = Console()


@command_meta(
    canonical_name="inspect.patterns",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Analyze pattern classification and violations across decision traces",
)
@core_command(dangerous=False, requires_context=True)
# ID: 7c9e7493-0e47-430b-ae30-753ae0cea7c3
def patterns_cmd(
    ctx: typer.Context,
    last: int = typer.Option(
        10, "--last", "-l", help="Number of recent decision traces to analyze"
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        "-p",
        help="Filter by specific pattern (e.g., 'action_pattern')",
    ),
):
    """
    Analyze pattern classification and violations across decision traces.

    This diagnostic tool helps understand:
    - Which patterns are being inferred
    - Why certain code triggers violations
    - Success/failure rates per pattern
    - Common misclassification patterns

    Examples:
        core-admin inspect patterns
        core-admin inspect patterns --last 20
        core-admin inspect patterns --pattern action_pattern
    """
    logger.info("\n[bold blue]🔍 Pattern Classification Analysis[/bold blue]\n")
    core_context: CoreContext = ctx.obj
    decisions_dir = core_context.git_service.repo_path / "reports" / "decisions"
    if not decisions_dir.exists():
        logger.info(
            "[yellow]No decision traces found. Run a development task first.[/yellow]"
        )
        return
    trace_files = sorted(
        decisions_dir.glob("trace_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:last]
    if not trace_files:
        logger.info("[yellow]No trace files found.[/yellow]")
        return
    pattern_stats = {}
    total_decisions = 0
    violations_by_pattern = {}
    for trace_file in trace_files:
        try:
            with open(trace_file) as f:
                trace_data = json.load(f)
            for decision in trace_data.get("decisions", []):
                total_decisions += 1
                context = decision.get("context", {})
                inferred_pattern = context.get("pattern_id", "unknown")
                if pattern and inferred_pattern != pattern:
                    continue
                if inferred_pattern not in pattern_stats:
                    pattern_stats[inferred_pattern] = {
                        "count": 0,
                        "violations": 0,
                        "files": set(),
                    }
                pattern_stats[inferred_pattern]["count"] += 1
                if decision.get("has_violations"):
                    pattern_stats[inferred_pattern]["violations"] += 1
                    if inferred_pattern not in violations_by_pattern:
                        violations_by_pattern[inferred_pattern] = []
                    violations_by_pattern[inferred_pattern].append(decision)
                target_file = context.get("target_file", "")
                if target_file:
                    pattern_stats[inferred_pattern]["files"].add(target_file)
        except Exception as e:
            logger.info("[yellow]Could not parse %s: %s[/yellow]", trace_file.name, e)
            continue
    if not pattern_stats:
        logger.info("[yellow]No pattern data found in traces.[/yellow]")
        return
    logger.info("[cyan]Analyzed %s trace files[/cyan]", len(trace_files))
    logger.info("[cyan]Total decisions: %s[/cyan]\n", total_decisions)
    table = Table(title="Pattern Classification Summary")
    table.add_column("Pattern", style="cyan")
    table.add_column("Uses", justify="right")
    table.add_column("Violations", justify="right")
    table.add_column("Success Rate", justify="right")
    table.add_column("Files", justify="right")
    for pattern_id, stats in sorted(
        pattern_stats.items(), key=lambda x: x[1]["count"], reverse=True
    ):
        uses = stats["count"]
        violations = stats["violations"]
        success_rate = (uses - violations) / uses * 100 if uses > 0 else 0
        files_count = len(stats["files"])
        status_color = (
            "green" if success_rate > 80 else "yellow" if success_rate > 50 else "red"
        )
        table.add_row(
            pattern_id,
            str(uses),
            str(violations),
            f"[{status_color}]{success_rate:.1f}%[/{status_color}]",
            str(files_count),
        )
    logger.info(table)
    if violations_by_pattern:
        logger.info("\n[bold red]Violation Details:[/bold red]\n")
        for pattern_id, violation_decisions in violations_by_pattern.items():
            logger.info(
                "[red]Pattern: %s (%s violations)[/red]",
                pattern_id,
                len(violation_decisions),
            )
            for i, decision in enumerate(violation_decisions[:3], 1):
                context = decision.get("context", {})
                logger.info("  %s. %s", i, context.get("target_file", "unknown"))
                logger.info("     Reason: %s", decision.get("rationale", "N/A")[:100])
            if len(violation_decisions) > 3:
                logger.info("  ... and %s more", len(violation_decisions) - 3)
            logger.info()


patterns_commands = [{"name": "patterns", "func": patterns_cmd}]
