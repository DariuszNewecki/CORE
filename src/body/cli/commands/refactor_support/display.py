# src/body/cli/commands/refactor_support/display.py

"""
Display formatting for refactoring analysis output.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table


# Module-level console for direct access
console = Console()


# ID: ee199bef-c985-43dc-a18f-f7118b34ef34
class RefactorDisplay:
    """Handles Rich-based display formatting for refactoring analysis."""

    def __init__(self):
        # Use module-level console
        self.console = console

    @staticmethod
    # ID: c3e6cf81-d429-444d-9de4-78e703338875
    def show_file_analysis(file_path: str, details: dict, target_value: float) -> None:
        """Display detailed analysis for a single file."""
        console.print(f"[bold cyan]🔍 Analyzing Modularity: {file_path}[/bold cyan]\n")

        score = details["total_score"]
        breakdown = details["breakdown"]

        # Determine status
        status, color = RefactorDisplay._get_status(score, target_value)
        console.print(
            f"[{color}]Status: {status} (Score: {score:.1f} / Target: <{target_value})[/{color}]\n"
        )

        # Score breakdown table
        RefactorDisplay._show_breakdown_table(breakdown, score)

        # Detailed analysis sections
        RefactorDisplay._show_responsibilities(details)
        RefactorDisplay._show_cohesion_warning(details)
        RefactorDisplay._show_coupling_warning(details)

    @staticmethod
    # ID: f244bee6-64c9-42ce-a1b3-86facb48024b
    def show_recommendations(recommendations: list[str]) -> None:
        """Display recommendations."""
        console.print("\n[bold green]💡 Recommended Improvements:[/bold green]")
        for rec in recommendations:
            console.print(f"  - {rec}")

    @staticmethod
    # ID: 1ff7e7ae-d258-4485-996f-c3e009272f9e
    def show_clean_file() -> None:
        """Display message for exceptionally clean files."""
        console.print("[bold green]✅ This file is exceptionally clean.[/bold green]")

    @staticmethod
    # ID: e65f7f69-5f89-4205-bb81-9e0f836c860f
    def show_candidates_table(
        candidates: list[dict], target_value: float, limit: int
    ) -> None:
        """Display table of refactoring candidates."""
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

    @staticmethod
    # ID: 86a8154f-6b90-43ec-9068-0a3a37688373
    def show_no_candidates() -> None:
        """Display message when no candidates exceed threshold."""
        console.print(
            "[bold green]✅ No files found exceeding the modularity threshold.[/bold green]"
        )

    @staticmethod
    # ID: 47d1f152-2c28-49c1-a5a0-7bb6628d6e87
    def show_stats(
        total_files: int,
        avg_score: float,
        target_value: float,
        high_risk: int,
        warning: int,
        healthy: int,
    ) -> None:
        """Display codebase statistics."""
        console.print("[bold cyan]📊 System Modularity Statistics[/bold cyan]\n")

        console.print(f"Total Files Analyzed : [bold]{total_files}[/bold]")
        console.print(f"Constitutional Target: <{target_value:.1f}")
        console.print(f"Average System Score : [bold]{avg_score:.1f}/100[/bold]\n")

        warning_level = target_value * 0.8
        console.print("[bold]Health Distribution (80% Gaussian Gauge):[/bold]")
        console.print(f"  🔴 High Risk (>{target_value:.1f})     : {high_risk} files")
        console.print(
            f"  🟡 Warning ({warning_level:.1f}-{target_value:.1f})  : {warning} files"
        )
        console.print(f"  🟢 Healthy (<{warning_level:.1f})     : {healthy} files")

    @staticmethod
    def _get_status(score: float, target_value: float) -> tuple[str, str]:
        """Determine status and color based on score."""
        if score > target_value:
            return "NON-COMPLIANT", "red"
        elif score > (target_value * 0.8):
            return "WARNING: BORDERLINE", "yellow"
        else:
            return "COMPLIANT", "green"

    @staticmethod
    def _show_breakdown_table(breakdown: dict, total_score: float) -> None:
        """Show modularity breakdown table."""
        table = Table(title="Modularity Breakdown", box=None)
        table.add_column("Dimension", style="cyan")
        table.add_column("Impact", justify="right")
        table.add_column("Max Weight", justify="right")

        table.add_row("Responsibilities", f"{breakdown['responsibilities']:.1f}", "35")
        table.add_row("Semantic Cohesion", f"{breakdown['cohesion']:.1f}", "25")
        table.add_row("Dependency Coupling", f"{breakdown['coupling']:.1f}", "25")
        table.add_row("Code Volume", f"{breakdown['size']:.1f}", "15")
        table.add_row(
            "[bold]TOTAL DEBT[/bold]", f"[bold]{total_score:.1f}[/bold]", "100"
        )

        console.print(table)

    @staticmethod
    def _show_responsibilities(details: dict) -> None:
        """Show detected responsibilities."""
        if details.get("responsibilities"):
            console.print(
                f"\n[bold]Detected Responsibilities ({len(details['responsibilities'])}):[/bold]"
            )
            for resp in details["responsibilities"]:
                console.print(f"  • {resp.replace('_', ' ').title()}")

    @staticmethod
    def _show_cohesion_warning(details: dict) -> None:
        """Show cohesion warning if applicable."""
        cohesion = details.get("cohesion", 1.0)
        if cohesion < 0.70:
            console.print(
                f"\n[bold yellow]⚠️ Low Semantic Cohesion:[/bold yellow] {cohesion:.2f}"
            )
            console.print("  Functions in this file may not belong together logically.")

    @staticmethod
    def _show_coupling_warning(details: dict) -> None:
        """Show coupling warning if applicable."""
        concern_count = details.get("concern_count", 0)
        if concern_count > 3:
            console.print(
                f"\n[bold yellow]⚠️ High Coupling:[/bold yellow] touches {concern_count} areas."
            )
            if details.get("concerns"):
                console.print(f"  Areas: {', '.join(details['concerns'])}")
