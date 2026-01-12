# src/body/cli/commands/refactor.py
"""
Refactoring analysis commands - identify modularization opportunities.

Constitutional enforcement of modularity rules:
- Single responsibility
- Semantic cohesion
- Import coupling
- Comprehensive refactor scoring
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

refactor_app = typer.Typer(
    help="Refactoring analysis and suggestions", no_args_is_help=True
)


@refactor_app.command("analyze")
@core_command(dangerous=False)
# ID: f1a2b3c4-d5e6-7a8b-9c0d-1e2f3a4b5c6d
async def analyze_file(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="File to analyze"),
) -> None:
    """
    Analyze a single file for refactoring opportunities.

    Checks:
    - Responsibility count
    - Semantic cohesion
    - Import coupling
    - Overall refactor score
    """
    core_context: CoreContext = ctx.obj
    checker = ModularityChecker()

    file = settings.REPO_PATH / file_path
    if not file.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]🔍 Analyzing: {file_path}[/bold cyan]\n")

    # Run all checks
    params_resp = {"max_responsibilities": 2}
    params_cohesion = {"min_cohesion": 0.70}
    params_coupling = {"max_concerns": 3}
    params_score = {"max_score": 60}

    resp_findings = checker.check_single_responsibility(file, params_resp)
    cohesion_findings = checker.check_semantic_cohesion(file, params_cohesion)
    coupling_findings = checker.check_import_coupling(file, params_coupling)
    score_findings = checker.check_refactor_score(file, params_score)

    # Display results
    if not any([resp_findings, cohesion_findings, coupling_findings, score_findings]):
        console.print("[bold green]✅ No refactoring issues detected[/bold green]")
        return

    # Build detailed report
    if score_findings:
        finding = score_findings[0]
        details = finding["details"]
        breakdown = details["breakdown"]

        # Header
        score = details["total_score"]
        severity = "URGENT" if score > 75 else "HIGH" if score > 60 else "MODERATE"
        color = "red" if score > 75 else "yellow" if score > 60 else "blue"

        console.print(
            f"[bold {color}]Refactor Score: {score:.1f}/100 ({severity})[/bold {color}]\n"
        )

        # Breakdown table
        table = Table(title="Score Breakdown", box=None)
        table.add_column("Component", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Max", justify="right")

        table.add_row(
            "Responsibilities",
            f"{breakdown['responsibilities']:.1f}",
            "40",
        )
        table.add_row(
            "Cohesion",
            f"{breakdown['cohesion']:.1f}",
            "25",
        )
        table.add_row(
            "Coupling",
            f"{breakdown['coupling']:.1f}",
            "20",
        )
        table.add_row(
            "Size",
            f"{breakdown['size']:.1f}",
            "5",
        )
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{score:.1f}[/bold]",
            "[bold]100[/bold]",
        )

        console.print(table)
        console.print()

        # Responsibilities
        if details["responsibilities"]:
            console.print("[bold]Responsibilities Found:[/bold]")
            for resp in details["responsibilities"]:
                console.print(f"  ❌ {resp}")
            console.print()

        # Cohesion
        if details["cohesion"] < 0.70:
            console.print(
                f"[bold]Semantic Cohesion:[/bold] {details['cohesion']:.2f} (min: 0.70)"
            )
            console.print("  ⚠️  Functions may not belong together\n")

        # Coupling
        if details["concerns"]:
            console.print(
                f"[bold]Coupling ({len(details['concerns'])} concerns):[/bold]"
            )
            for concern in details["concerns"]:
                console.print(f"  • {concern}")
            console.print()

        # Suggestion
        console.print("[bold]💡 Suggested Actions:[/bold]")

        if details["responsibility_count"] > 2:
            console.print("  1. Split into separate modules by responsibility")
        if details["cohesion"] < 0.70:
            console.print("  2. Group related functions into cohesive modules")
        if len(details["concerns"]) > 3:
            console.print("  3. Reduce coupling by extracting service layers")
        if details["lines_of_code"] > 400:
            console.print("  4. Break large file into smaller, focused modules")


@refactor_app.command("suggest")
@core_command(dangerous=False)
# ID: a2b3c4d5-e6f7-8a9b-0c1d-2e3f4a5b6c7d
async def suggest_candidates(
    ctx: typer.Context,
    min_score: float = typer.Option(
        60.0, "--min-score", help="Minimum refactor score to report"
    ),
    limit: int = typer.Option(20, "--limit", help="Max candidates to show"),
) -> None:
    """
    Scan entire codebase for refactoring candidates.

    Sorts by refactor score (highest first) and shows files
    that exceed the minimum threshold.
    """
    console.print(
        f"[bold cyan]🔍 Scanning codebase for refactoring candidates (score >= {min_score})...[/bold cyan]\n"
    )

    checker = ModularityChecker()
    candidates = []

    # Directories to skip
    skip_dirs = {".venv", "venv", ".git", "work", "var", "__pycache__", ".pytest_cache"}

    # Scan all Python files in src/ only
    for file in settings.REPO_PATH.rglob("*.py"):
        # Skip if in excluded directories
        if any(skip_dir in file.parts for skip_dir in skip_dirs):
            continue

        # Only scan src/ and tests/ directories
        rel_path = file.relative_to(settings.REPO_PATH)
        if not (str(rel_path).startswith("src/") or str(rel_path).startswith("tests/")):
            continue

        # Skip tests for now (focus on src/)
        if "/tests/" in str(file):
            continue

        try:
            findings = checker.check_refactor_score(
                file,
                {"max_score": min_score - 0.01},  # Get all above threshold
            )

            if findings:
                details = findings[0]["details"]
                candidates.append(
                    {
                        "file": rel_path,
                        "score": details["total_score"],
                        "responsibilities": details["responsibility_count"],
                        "cohesion": details["cohesion"],
                        "concerns": len(details["concerns"]),
                        "loc": details["lines_of_code"],
                    }
                )
        except Exception as e:
            logger.debug("Failed to analyze %s: %s", file, e)
            continue

    if not candidates:
        console.print(
            f"[bold green]✅ No files found with refactor score >= {min_score}[/bold green]"
        )
        return

    # Sort by score (descending)
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Display table
    table = Table(title=f"Refactoring Candidates (Top {min(limit, len(candidates))})")
    table.add_column("File", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Resp", justify="right")
    table.add_column("Cohesion", justify="right")
    table.add_column("Concerns", justify="right")
    table.add_column("LOC", justify="right")

    for candidate in candidates[:limit]:
        score = candidate["score"]
        color = "red" if score > 75 else "yellow" if score > 60 else "blue"

        table.add_row(
            str(candidate["file"]),
            f"[{color}]{score:.1f}[/{color}]",
            str(candidate["responsibilities"]),
            f"{candidate['cohesion']:.2f}",
            str(candidate["concerns"]),
            str(candidate["loc"]),
        )

    console.print(table)
    console.print(
        f"\n[dim]Found {len(candidates)} total candidates (showing top {min(limit, len(candidates))})[/dim]"
    )
    console.print(
        "[dim]Use 'core-admin refactor analyze <file>' for detailed analysis[/dim]"
    )


@refactor_app.command("stats")
@core_command(dangerous=False)
# ID: b3c4d5e6-f7a8-9b0c-1d2e-3f4a5b6c7d8e
async def show_stats(ctx: typer.Context) -> None:
    """
    Show codebase modularity statistics.

    Provides overview of:
    - Average refactor score
    - Distribution of responsibility counts
    - Cohesion metrics
    - Coupling distribution
    """
    console.print("[bold cyan]📊 Codebase Modularity Statistics[/bold cyan]\n")

    checker = ModularityChecker()
    all_scores = []
    resp_counts = []
    cohesion_scores = []
    concern_counts = []

    # Analyze all Python files
    for file in settings.REPO_PATH.rglob("*.py"):
        if "/tests/" in str(file) or "/migrations/" in str(file):
            continue

        try:
            findings = checker.check_refactor_score(file, {"max_score": 1000})

            if findings:
                details = findings[0]["details"]
                all_scores.append(details["total_score"])
                resp_counts.append(details["responsibility_count"])
                cohesion_scores.append(details["cohesion"])
                concern_counts.append(len(details["concerns"]))
        except Exception:
            continue

    if not all_scores:
        console.print("[yellow]No files analyzed[/yellow]")
        return

    # Calculate stats
    avg_score = sum(all_scores) / len(all_scores)
    avg_resp = sum(resp_counts) / len(resp_counts)
    avg_cohesion = sum(cohesion_scores) / len(cohesion_scores)
    avg_concerns = sum(concern_counts) / len(concern_counts)

    high_score = sum(1 for s in all_scores if s > 75)
    medium_score = sum(1 for s in all_scores if 60 < s <= 75)
    low_score = sum(1 for s in all_scores if s <= 60)

    # Display
    console.print(f"[bold]Files Analyzed:[/bold] {len(all_scores)}\n")

    console.print("[bold]Average Metrics:[/bold]")
    console.print(f"  Refactor Score: {avg_score:.1f}/100")
    console.print(f"  Responsibilities: {avg_resp:.1f}")
    console.print(f"  Cohesion: {avg_cohesion:.2f}")
    console.print(f"  Concerns: {avg_concerns:.1f}\n")

    console.print("[bold]Score Distribution:[/bold]")
    console.print(
        f"  🔴 High (>75):   {high_score} files ({high_score/len(all_scores)*100:.1f}%)"
    )
    console.print(
        f"  🟡 Medium (60-75): {medium_score} files ({medium_score/len(all_scores)*100:.1f}%)"
    )
    console.print(
        f"  🟢 Low (<60):    {low_score} files ({low_score/len(all_scores)*100:.1f}%)\n"
    )

    health = (
        "good" if avg_score < 50 else "fair" if avg_score < 65 else "needs attention"
    )
    console.print(f"[bold]Overall Health:[/bold] {health}")
