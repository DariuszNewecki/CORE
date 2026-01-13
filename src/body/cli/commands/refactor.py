# src/body/cli/commands/refactor.py
"""
Refactoring analysis commands - identify modularization opportunities.

Constitutional enforcement of modularity rules:
- Single responsibility
- Semantic cohesion
- Import coupling
- Comprehensive refactor scoring

This module pulls its thresholds directly from the Constitution (.intent).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.cli_utils import core_command
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

refactor_app = typer.Typer(
    help="Refactoring analysis and suggestions", no_args_is_help=True
)


def _get_modularity_threshold() -> float:
    """
    Retrieves the authoritative 'max_score' from the Constitution.
    Path: .intent/enforcement/mappings/architecture/modularity.yaml
    """
    try:
        # We look into the 'Mind' (.intent) to find the current law
        loader = EnforcementMappingLoader(settings.REPO_PATH / ".intent")
        strategy = loader.get_enforcement_strategy(
            "modularity.refactor_score_threshold"
        )
        if strategy and "params" in strategy:
            return float(strategy["params"].get("max_score", 60.0))
    except Exception as e:
        logger.debug("Could not load modularity threshold from Constitution: %s", e)

    return 60.0  # Safe fallback if the Mind is unreadable


def _get_source_files() -> Iterable[Path]:
    """
    Standardized file enumerator. Ensures we don't analyze junk/temp folders.
    """
    skip_dirs = {
        ".venv",
        "venv",
        ".git",
        "work",
        "var",
        "__pycache__",
        ".pytest_cache",
        "tests",
        "migrations",
        "reports",
    }
    src_root = settings.REPO_PATH / "src"
    if not src_root.exists():
        return []

    for file in src_root.rglob("*.py"):
        if any(part in file.parts for part in skip_dirs):
            continue
        yield file


@refactor_app.command("analyze")
@core_command(dangerous=False)
# ID: f1a2b3c4-d5e6-7a8b-9c0d-1e2f3a4b5c6d
async def analyze_file(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="File to analyze"),
) -> None:
    """
    Analyze a single file for refactoring opportunities.
    """
    checker = ModularityChecker()
    target_value = _get_modularity_threshold()

    # Locate the file on disk
    target_file = (settings.REPO_PATH / file_path).resolve()
    if not target_file.exists() or not target_file.is_file():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]🔍 Analyzing Modularity: {file_path}[/bold cyan]\n")

    # Ask the logic engine for the comprehensive score.
    # We pass 0 as the 'max_score' param to ensure the logic engine
    # returns the full data even for healthy files.
    score_findings = checker.check_refactor_score(target_file, {"max_score": 0})

    if not score_findings:
        console.print("[bold green]✅ This file is exceptionally clean.[/bold green]")
        return

    details = score_findings[0]["details"]
    breakdown = details["breakdown"]
    score = details["total_score"]

    # --- 80% Gaussian Gauge Logic ---
    if score > target_value:
        status = "NON-COMPLIANT"
        color = "red"
    elif score > (target_value * 0.8):
        status = "WARNING: BORDERLINE"
        color = "yellow"
    else:
        status = "COMPLIANT"
        color = "green"

    console.print(
        f"[{color}]Status: {status} (Score: {score:.1f} / Target: <{target_value})[/{color}]\n"
    )

    # Display the score breakdown table
    table = Table(title="Modularity Breakdown", box=None)
    table.add_column("Dimension", style="cyan")
    table.add_column("Impact", justify="right")
    table.add_column("Max Weight", justify="right")

    table.add_row("Responsibilities", f"{breakdown['responsibilities']:.1f}", "40")
    table.add_row("Semantic Cohesion", f"{breakdown['cohesion']:.1f}", "25")
    table.add_row("Dependency Coupling", f"{breakdown['coupling']:.1f}", "20")
    table.add_row("Code Volume", f"{breakdown['size']:.1f}", "15")
    table.add_row("[bold]TOTAL DEBT[/bold]", f"[bold]{score:.1f}[/bold]", "100")
    console.print(table)

    # Detailed Analysis section (Responsibilities)
    if details.get("responsibilities"):
        console.print(
            f"\n[bold]Detected Responsibilities ({len(details['responsibilities'])}):[/bold]"
        )
        for resp in details["responsibilities"]:
            console.print(f"  ❌ {resp.replace('_', ' ').title()}")

    # Detailed Analysis section (Cohesion & Coupling)
    if details.get("cohesion", 1.0) < 0.70:
        console.print(
            f"\n[bold yellow]⚠️ Low Semantic Cohesion:[/bold yellow] {details['cohesion']:.2f}"
        )
        console.print("  Functions in this file may not belong together logically.")

    if details.get("concern_count", 0) > 3:
        console.print(
            f"\n[bold yellow]⚠️ High Coupling:[/bold yellow] touches {details['concern_count']} areas."
        )
        if details.get("concerns"):
            console.print(f"  Areas: {', '.join(details['concerns'])}")

    # Logic-driven recommendations
    console.print("\n[bold green]💡 Recommended Improvements:[/bold green]")
    if breakdown["responsibilities"] > 20:
        console.print(
            "  - [bold]Split Module:[/bold] This file is doing too many things. Extract logic into new files."
        )
    if breakdown["cohesion"] > 12:
        console.print(
            "  - [bold]Refine Logic:[/bold] Group related functions more tightly to improve focus."
        )
    if breakdown["coupling"] > 10:
        console.print(
            "  - [bold]Decouple:[/bold] Reduce external imports; use 'shared' services instead of direct calls."
        )
    if details.get("lines_of_code", 0) > 400:
        console.print(
            "  - [bold]Reduce Volume:[/bold] File is physically too long. Move helpers to 'shared/utils'."
        )


@refactor_app.command("suggest")
@core_command(dangerous=False)
# ID: a2b3c4d5-e6f7-8a9b-0c1d-2e3f4a5b6c7d
async def suggest_candidates(
    ctx: typer.Context,
    min_score: float = typer.Option(
        None, "--min-score", help="Filter by score (defaults to Constitution limit)"
    ),
    limit: int = typer.Option(10, "--limit", help="Number of files to show"),
) -> None:
    """
    Rank and suggest files that need refactoring based on current score.
    """
    target_value = _get_modularity_threshold()
    filter_score = min_score if min_score is not None else target_value

    console.print(
        f"[bold cyan]🔍 Scanning Codebase (Target Score: <{target_value})...[/bold cyan]\n"
    )

    checker = ModularityChecker()
    candidates = []

    for file in _get_source_files():
        try:
            findings = checker.check_refactor_score(file, {"max_score": 0})
            if findings:
                data = findings[0]["details"]
                if data["total_score"] >= filter_score:
                    candidates.append(
                        {
                            "file": file.relative_to(settings.REPO_PATH),
                            "score": data["total_score"],
                            "resp": data["responsibility_count"],
                            "loc": data.get("lines_of_code", 0),
                        }
                    )
        except Exception:
            continue

    if not candidates:
        console.print(
            "[bold green]✅ No files found exceeding the modularity threshold.[/bold green]"
        )
        return

    # Sort so the highest scores (most complex files) are at the top
    candidates.sort(key=lambda x: x["score"], reverse=True)

    table = Table(title=f"Refactoring Candidates (Top {limit})")
    table.add_column("File Path", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Resp.", justify="right")
    table.add_column("Lines", justify="right")

    for c in candidates[:limit]:
        color = "red" if c["score"] > target_value else "yellow"
        table.add_row(
            str(c["file"]),
            f"[{color}]{c['score']:.1f}[/{color}]",
            str(c["resp"]),
            str(c["loc"]),
        )

    console.print(table)


@refactor_app.command("stats")
@core_command(dangerous=False)
# ID: b3c4d5e6-f7a8-9b0c-1d2e-3f4a5b6c7d8e
async def show_stats(ctx: typer.Context) -> None:
    """
    Show aggregate codebase modularity health using Gaussian-derived risk tiers.
    """
    console.print("[bold cyan]📊 System Modularity Statistics[/bold cyan]\n")

    checker = ModularityChecker()
    target_value = _get_modularity_threshold()
    warning_level = target_value * 0.8  # The 80% mark

    scores = []
    for file in _get_source_files():
        try:
            findings = checker.check_refactor_score(file, {"max_score": 0})
            if findings:
                scores.append(findings[0]["details"]["total_score"])
        except Exception:
            continue

    if not scores:
        console.print("[yellow]No Python files found for analysis.[/yellow]")
        return

    avg = sum(scores) / len(scores)
    high_risk_count = sum(1 for s in scores if s > target_value)
    warning_count = sum(1 for s in scores if warning_level < s <= target_value)
    healthy_count = len(scores) - high_risk_count - warning_count

    console.print(f"Total Files Analyzed : [bold]{len(scores)}[/bold]")
    console.print(f"Constitutional Target: <{target_value:.1f}")
    console.print(f"Average System Score : [bold]{avg:.1f}/100[/bold]\n")

    console.print("[bold]Health Distribution (80% Gaussian Gauge):[/bold]")
    console.print(f"  🔴 High Risk (>{target_value:.1f})     : {high_risk_count} files")
    console.print(
        f"  🟡 Warning ({warning_level:.1f}-{target_value:.1f})  : {warning_count} files"
    )
    console.print(f"  🟢 Healthy (<{warning_level:.1f})     : {healthy_count} files")
