# src/body/cli/commands/fix/provider_refactor.py
"""
CLI command for analyzing settings → provider refactoring needs.

This command analyzes Mind/Will layers and generates a report on what needs
to be refactored to use the provider pattern (IntentRepository, FileProvider).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from features.maintenance.refactor_to_providers import (
    analyze_layer_for_refactoring,
    generate_refactoring_report,
)
from shared.cli_utils import core_command
from shared.config import settings

from . import fix_app


console = Console()


@fix_app.command("analyze-providers")
@core_command(dangerous=False, confirmation=False)
# ID: d3e4f5a6-b7c8-9012-3456-789012abcdef
async def analyze_provider_refactoring_cmd(
    ctx: typer.Context,
    layers: str = typer.Option(
        "mind,will", "--layers", help="Comma-separated layers to analyze"
    ),
    save_report: bool = typer.Option(
        True, "--save-report/--no-save-report", help="Save detailed report to file"
    ),
) -> None:
    """
    Analyze settings imports that should use provider pattern.

    This command identifies files in Mind/Will layers that directly import
    settings and should instead use:
    - IntentRepository for .intent/ access
    - repo_path parameters for path needs
    - FileProvider for other file reads

    The analysis categorizes files by automation potential:
    - High confidence: Can be automatically refactored
    - Manual review: Requires human judgment
    - Skip: Already compliant or not applicable
    """
    layer_list = [layer.strip() for layer in layers.split(",")]

    console.print(
        "\n[bold cyan]Constitutional Settings Refactoring Analysis[/bold cyan]"
    )
    console.print(f"Analyzing layers: {', '.join(layer_list)}\n")

    all_results = {}

    for layer in layer_list:
        with console.status(f"[bold green]Analyzing {layer} layer..."):
            results = await analyze_layer_for_refactoring(settings.REPO_PATH, layer)

        if "error" in results:
            console.print(f"[red]Error:[/red] {results['error']}")
            continue

        all_results[layer] = results

        # Print summary table
        table = Table(title=f"{layer.upper()} Layer Summary")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")

        summary = results["summary"]
        automatable = summary["intent_repository"] + summary["repo_path_param"]

        table.add_row("Total files analyzed", str(results["analyzed"]))
        table.add_row("", "")
        table.add_row("[green]Automatable (high confidence)", str(automatable))
        table.add_row(
            "  └─ IntentRepository pattern", str(summary["intent_repository"])
        )
        table.add_row("  └─ Repo path parameter", str(summary["repo_path_param"]))
        table.add_row("[yellow]Manual review needed", str(summary["manual_review"]))
        table.add_row("[dim]Already compliant", str(summary["skip"]))

        console.print(table)
        console.print()

    # Generate and save detailed report
    if save_report and all_results:
        report_lines = []
        for layer, results in all_results.items():
            report = generate_refactoring_report(results)
            report_lines.append(report)

        full_report = "\n\n".join(report_lines)

        report_path = (
            settings.REPO_PATH / "var" / "reports" / "provider_refactoring_analysis.txt"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(full_report)

        console.print(f"[bold]📊 Detailed report saved to:[/bold] {report_path}")

    # Summary across all layers
    if len(all_results) > 1:
        total_automatable = sum(
            r["summary"]["intent_repository"] + r["summary"]["repo_path_param"]
            for r in all_results.values()
        )
        total_manual = sum(r["summary"]["manual_review"] for r in all_results.values())

        console.print("\n[bold]Overall Summary:[/bold]")
        console.print(
            f"  Files that can be automatically refactored: [green]{total_automatable}[/green]"
        )
        console.print(f"  Files needing manual review: [yellow]{total_manual}[/yellow]")

    console.print("\n[dim]Next steps:[/dim]")
    console.print("  1. Review the detailed report")
    console.print("  2. Start with high-confidence IntentRepository migrations")
    console.print("  3. Handle manual review cases individually")
    console.print("  4. Run constitutional audit to verify compliance\n")
