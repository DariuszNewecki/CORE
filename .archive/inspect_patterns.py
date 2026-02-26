# src/body/cli/commands/inspect_patterns.py
"""
Diagnostic tool to analyze pattern classification and violations.
Helps understand why certain code triggers pattern violations.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from shared.context import CoreContext


console = Console()


# ID: b14188e7-a65e-4b40-b3e6-ac565dd08cfb
def inspect_patterns(
    ctx: typer.Context,
    last: int = typer.Option(
        10, "--last", "-l", help="Number of recent decision traces to analyze"
    ),
    pattern: str = typer.Option(
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
    """
    console.print("\n[bold blue]🔍 Pattern Classification Analysis[/bold blue]\n")

    # Find all decision traces
    core_context: CoreContext = ctx.obj
    decisions_dir = core_context.git_service.repo_path / "reports" / "decisions"
    if not decisions_dir.exists():
        console.print(
            "[yellow]No decision traces found. Run a development task first.[/yellow]"
        )
        return

    trace_files = sorted(
        decisions_dir.glob("trace_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:last]

    if not trace_files:
        console.print("[yellow]No trace files found.[/yellow]")
        return

    console.print(f"Analyzing {len(trace_files)} most recent traces...\n")

    # Analyze each trace
    pattern_stats = {}
    violation_cases = []

    for trace_file in trace_files:
        with open(trace_file) as f:
            trace_data = json.load(f)

        session_id = trace_data["session_id"]
        decisions = trace_data.get("decisions", [])

        # Extract pattern info
        patterns_used = set()
        had_violations = False
        violation_count = 0

        for decision in decisions:
            if decision["decision_type"] == "llm_generation":
                pattern_id = decision.get("context", {}).get("pattern_id")
                if pattern_id:
                    patterns_used.add(pattern_id)

            if decision["decision_type"] == "pattern_correction":
                had_violations = True
                violation_count = decision.get("context", {}).get("violations", 0)

        # Track stats per pattern
        for pat in patterns_used:
            if pat not in pattern_stats:
                pattern_stats[pat] = {
                    "total": 0,
                    "violations": 0,
                    "sessions": [],
                }
            pattern_stats[pat]["total"] += 1
            if had_violations:
                pattern_stats[pat]["violations"] += 1
            pattern_stats[pat]["sessions"].append(
                {
                    "session_id": session_id,
                    "had_violations": had_violations,
                    "violation_count": violation_count,
                }
            )

        # Record violation cases
        if had_violations and (
            not pattern or (patterns_used and next(iter(patterns_used)) == pattern)
        ):
            violation_cases.append(
                {
                    "session_id": session_id,
                    "patterns": list(patterns_used),
                    "violation_count": violation_count,
                    "trace_file": trace_file.name,
                }
            )

    # Display summary table
    if pattern_stats:
        table = Table(title="Pattern Usage Summary")
        table.add_column("Pattern", style="cyan")
        table.add_column("Total Uses", justify="right")
        table.add_column("Violations", justify="right")
        table.add_column("Success Rate", justify="right")

        for pat, stats in sorted(pattern_stats.items()):
            total = stats["total"]
            violations = stats["violations"]
            success_rate = ((total - violations) / total * 100) if total > 0 else 0

            rate_color = (
                "green"
                if success_rate >= 80
                else "yellow" if success_rate >= 50 else "red"
            )

            table.add_row(
                pat,
                str(total),
                str(violations),
                f"[{rate_color}]{success_rate:.1f}%[/{rate_color}]",
            )

        console.print(table)

    # Display violation cases
    if violation_cases:
        console.print(
            f"\n[bold red]❌ Sessions with Violations ({len(violation_cases)})[/bold red]\n"
        )

        for case in violation_cases[:10]:  # Show max 10
            console.print(f"Session: [yellow]{case['session_id']}[/yellow]")
            console.print(f"  Patterns: {', '.join(case['patterns'])}")
            console.print(f"  Violations: {case['violation_count']}")
            console.print(f"  Trace: {case['trace_file']}")
            console.print()

    # Recommendations
    console.print("[bold green]💡 Recommendations[/bold green]")

    for pat, stats in pattern_stats.items():
        success_rate = (
            ((stats["total"] - stats["violations"]) / stats["total"] * 100)
            if stats["total"] > 0
            else 0
        )

        if success_rate < 60:
            console.print(
                f"  ⚠️  [yellow]{pat}[/yellow]: Low success rate ({success_rate:.1f}%)"
            )
            console.print(
                "      → Review pattern requirements or improve classification"
            )

        if pat == "action_pattern" and stats["violations"] > stats["total"] * 0.3:
            console.print("  ⚠️  [yellow]action_pattern[/yellow]: High violation rate")
            console.print("      → May be over-applied to pure functions")
            console.print("      → Consider using 'pure_function' classification")

    console.print()
