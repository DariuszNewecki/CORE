# src/cli/commands/refactor_support/display.py
"""
Display formatting for refactoring analysis output.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from rich.console import Console
from rich.table import Table


console = Console()


# ID: faf1e919-5ae7-4a63-8e3b-89847123dd51
class RefactorDisplay:
    """Handles Rich-based display formatting for refactoring analysis."""

    def __init__(self):
        self.console = console

    @staticmethod
    # ID: 903e0fd9-1162-4d90-951c-9cc4ed2497f5
    def show_file_analysis(file_path: str, details: dict, target_value: float) -> None:
        """Display detailed analysis for a single file."""
        logger.info("[bold cyan]🔍 Analyzing Modularity: %s[/bold cyan]\n", file_path)
        score = details["total_score"]
        breakdown = details["breakdown"]
        status, color = RefactorDisplay._get_status(score, target_value)
        logger.info(
            "[%s]Status: %s (Score: %s / Target: <%s)[/%s]\n",
            color,
            status,
            score,
            target_value,
            color,
        )
        RefactorDisplay._show_breakdown_table(breakdown, score)
        RefactorDisplay._show_responsibilities(details)
        RefactorDisplay._show_cohesion_warning(details)
        RefactorDisplay._show_coupling_warning(details)

    @staticmethod
    # ID: 1f9a5dcb-9ae6-45a6-bce0-e3a98c74ba97
    def show_recommendations(recommendations: list[str]) -> None:
        """Display recommendations."""
        logger.info("\n[bold green]💡 Recommended Improvements:[/bold green]")
        for rec in recommendations:
            logger.info("  - %s", rec)

    @staticmethod
    # ID: f9985b46-2553-46df-9e10-fb86eceb56ea
    def show_clean_file() -> None:
        """Display message for exceptionally clean files."""
        logger.info("[bold green]✅ This file is exceptionally clean.[/bold green]")

    @staticmethod
    # ID: 9f129067-663c-4ec0-944a-59c3aac772a3
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
        logger.info(table)

    @staticmethod
    # ID: bedaeaa7-18e6-4ad9-b47e-ac1faa3e70f5
    def show_no_candidates() -> None:
        """Display message when no candidates exceed threshold."""
        logger.info(
            "[bold green]✅ No files found exceeding the modularity threshold.[/bold green]"
        )

    @staticmethod
    # ID: fb2cc8dc-a8e7-4310-8a91-fd89a6b203ea
    def show_stats(
        total_files: int,
        avg_score: float,
        target_value: float,
        high_risk: int,
        warning: int,
        healthy: int,
    ) -> None:
        """Display codebase statistics."""
        logger.info("[bold cyan]📊 System Modularity Statistics[/bold cyan]\n")
        logger.info("Total Files Analyzed : [bold]%s[/bold]", total_files)
        logger.info("Constitutional Target: <%s", target_value)
        logger.info("Average System Score : [bold]%s/100[/bold]\n", avg_score)
        warning_level = target_value * 0.8
        logger.info("[bold]Health Distribution (80% Gaussian Gauge):[/bold]")
        logger.info("  🔴 High Risk (>%s)     : %s files", target_value, high_risk)
        logger.info(
            "  🟡 Warning (%s-%s)  : %s files", warning_level, target_value, warning
        )
        logger.info("  🟢 Healthy (<%s)     : %s files", warning_level, healthy)

    @staticmethod
    def _get_status(score: float, target_value: float) -> tuple[str, str]:
        """Determine status and color based on score."""
        if score > target_value:
            return ("NON-COMPLIANT", "red")
        elif score > target_value * 0.8:
            return ("WARNING: BORDERLINE", "yellow")
        else:
            return ("COMPLIANT", "green")

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
        logger.info(table)

    @staticmethod
    def _show_responsibilities(details: dict) -> None:
        """Show detected responsibilities."""
        if details.get("responsibilities"):
            logger.info(
                "\n[bold]Detected Responsibilities (%s):[/bold]",
                len(details["responsibilities"]),
            )
            for resp in details["responsibilities"]:
                logger.info("  • %s", resp.replace("_", " ").title())

    @staticmethod
    def _show_cohesion_warning(details: dict) -> None:
        """Show cohesion warning if applicable."""
        cohesion = details.get("cohesion", 1.0)
        if cohesion < 0.7:
            logger.info(
                "\n[bold yellow]⚠️ Low Semantic Cohesion:[/bold yellow] %s", cohesion
            )
            logger.info("  Functions in this file may not belong together logically.")

    @staticmethod
    def _show_coupling_warning(details: dict) -> None:
        """Show coupling warning if applicable."""
        concern_count = details.get("concern_count", 0)
        if concern_count > 3:
            logger.info(
                "\n[bold yellow]⚠️ High Coupling:[/bold yellow] touches %s areas.",
                concern_count,
            )
            if details.get("concerns"):
                logger.info("  Areas: %s", ", ".join(details["concerns"]))
