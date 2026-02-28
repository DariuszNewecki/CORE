# src/cli/resources/admin/legacy.py
# ID: d6e7f8a9-b0c1-2345-defa-234567890123

"""
Admin Legacy Command - Technical Debt Map.

Scans the codebase for markers that indicate workarounds, healed
violations, circular import patches, and unresolved TODOs.

Output tells you exactly where to focus cleanup work.

Constitutional Alignment:
- Behavior: READ (pure scan, no mutations)
- Layer: MIND (governance visibility)
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.logic.legacy_scan_logic import (
    LEGACY_MARKERS,
    LegacyScanResult,
    get_top_debt_files,
    scan_for_legacy_markers,
)
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("legacy")
@command_meta(
    canonical_name="admin.legacy",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    summary="Scan codebase for legacy markers and technical debt.",
)
@core_command(dangerous=False, requires_context=False)
# ID: e7f8a9b0-c1d2-3456-efab-345678901234
def admin_legacy_cmd(
    ctx: typer.Context,
    severity: str = typer.Option(
        None,
        "--severity",
        "-s",
        help="Filter by severity: high, medium, low",
    ),
    top: int = typer.Option(
        20,
        "--top",
        "-n",
        help="Show top N files by debt load (default: 20)",
    ),
    detail: bool = typer.Option(
        False,
        "--detail",
        "-d",
        help="Show individual lines, not just file summary",
    ),
    marker: str = typer.Option(
        None,
        "--marker",
        "-m",
        help="Filter by marker type (e.g. HEALED, TODO, DEPRECATED)",
    ),
) -> None:
    """
    Find every HEALED, CONSTITUTIONAL FIX, CIRCULARITY FIX, DEPRECATED,
    TODO, FIXME, HACK, WORKAROUND and LEGACY marker in the codebase.

    This is your cleanup map. Start with high severity, highest count files.

    Examples:
        core-admin admin legacy
        core-admin admin legacy --severity high
        core-admin admin legacy --marker HEALED --detail
        core-admin admin legacy --top 5 --detail
    """
    repo_root = Path.cwd()

    # Validate options
    if severity and severity not in ("high", "medium", "low"):
        console.print("[red]Invalid severity. Choose: high, medium, low[/red]")
        raise typer.Exit(1)

    if marker:
        marker = marker.upper()
        if marker not in LEGACY_MARKERS:
            valid = ", ".join(LEGACY_MARKERS.keys())
            console.print(f"[red]Unknown marker '{marker}'. Valid: {valid}[/red]")
            raise typer.Exit(1)

    console.print(
        f"\n[bold cyan]🔍 Scanning for technical debt in {repo_root}/src ...[/bold cyan]\n"
    )

    result = scan_for_legacy_markers(
        repo_root=repo_root,
        scan_dirs=["src"],
        severity_filter=severity,
    )

    if marker:
        result = _filter_by_marker(result, marker)

    if result.total_hits == 0:
        console.print("[green]✅ No legacy markers found. Clean codebase![/green]\n")
        return

    _print_summary_panel(result)
    _print_marker_breakdown(result)
    _print_file_table(result, top=top, detail=detail)


# ---------------------------------------------------------------------------
# Private rendering helpers
# ---------------------------------------------------------------------------


# ID: f8a9b0c1-d2e3-4567-fabc-456789012345
def _filter_by_marker(result: LegacyScanResult, marker: str) -> LegacyScanResult:
    """Return a new result containing only hits for the given marker."""
    from cli.logic.legacy_scan_logic import FileLegacySummary

    filtered = []
    for file_summary in result.files_with_hits:
        matching = [h for h in file_summary.hits if h.marker == marker]
        if matching:
            fs = FileLegacySummary(file_path=file_summary.file_path)
            fs.hits = matching
            filtered.append(fs)

    result.files_with_hits = filtered
    return result


# ID: a9b0c1d2-e3f4-5678-abcd-567890123456
def _print_summary_panel(result: LegacyScanResult) -> None:
    """Print the top-level summary panel."""
    high = result.total_high_severity
    total = result.total_hits
    files = len(result.files_with_hits)

    high_color = "red" if high > 0 else "green"
    summary = (
        f"Files scanned : {result.files_scanned}\n"
        f"Files with debt: {files}\n"
        f"Total markers : {total}\n"
        f"[{high_color}]High severity : {high}[/{high_color}]"
    )
    console.print(
        Panel(summary, title="[bold]Technical Debt Summary[/bold]", expand=False)
    )


# ID: b0c1d2e3-f4a5-6789-bcde-678901234567
def _print_marker_breakdown(result: LegacyScanResult) -> None:
    """Print per-marker count table."""
    totals = result.marker_totals
    if not totals:
        return

    table = Table(
        title="Marker Breakdown",
        header_style="bold magenta",
        show_header=True,
        show_lines=False,
    )
    table.add_column("Marker", style="cyan", min_width=20)
    table.add_column("Count", justify="right", min_width=6)
    table.add_column("Severity", min_width=8)
    table.add_column("Meaning", style="dim")

    for marker_key, count in totals.items():
        info = LEGACY_MARKERS.get(marker_key, {})
        severity = info.get("severity", "?")
        color = info.get("color", "white")
        label = info.get("description", "")
        table.add_row(
            f"[{color}]{marker_key}[/{color}]",
            str(count),
            f"[{color}]{severity}[/{color}]",
            label,
        )

    console.print(table)
    console.print()


# ID: c1d2e3f4-a5b6-7890-cdef-789012345678
def _print_file_table(
    result: LegacyScanResult,
    top: int,
    detail: bool,
) -> None:
    """Print per-file debt table, optionally with line detail."""
    files = get_top_debt_files(result, limit=top)

    if not files:
        return

    table = Table(
        title=f"Top {top} Files by Debt Load",
        header_style="bold magenta",
        show_header=True,
        show_lines=detail,
    )
    table.add_column("File", style="cyan")
    table.add_column("Total", justify="right", min_width=6)
    table.add_column("High", justify="right", min_width=6, style="red")
    table.add_column("Markers")

    for file_summary in files:
        marker_str = ", ".join(f"{k}x{v}" for k, v in file_summary.by_marker.items())
        table.add_row(
            file_summary.file_path,
            str(file_summary.total),
            str(file_summary.high_severity_count),
            marker_str,
        )

        if detail:
            for hit in file_summary.hits:
                table.add_row(
                    f"  [dim]L{hit.line_number}[/dim]",
                    "",
                    "",
                    f"[{hit.color}]{hit.marker}[/{hit.color}]  "
                    f"[dim]{hit.line_content}[/dim]",
                )

    console.print(table)
    console.print(
        "\n[dim]Run with --detail to see individual lines. "
        "Run with --severity high to focus on critical debt.[/dim]\n"
    )
