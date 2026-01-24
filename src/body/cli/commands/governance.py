# src/body/cli/commands/governance.py
"""
Constitutional governance commands - enforcement coverage and verification.

CONSTITUTIONAL FIX:
- Aligned with 'architecture.max_file_size' (Modularized).
- Delegates heavy processing to 'body.cli.logic.governance_logic'.
- Maintained 'governance.artifact_mutation.traceable' fixes.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from body.cli.logic import governance_logic as logic
from shared.cli_utils import core_command
from shared.context import CoreContext


console = Console()
governance_app = typer.Typer(
    help="Constitutional governance visibility and verification.", no_args_is_help=True
)


@governance_app.command("coverage")
@core_command(dangerous=False, requires_context=True)
# ID: 0753d0ea-9942-431f-b013-5ee5d09eb782
def enforcement_coverage(
    ctx: typer.Context,
    format: str = typer.Option(
        "summary",
        "--format",
        "-f",
        help="Output format: summary|hierarchical|json",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file instead of console",
    ),
) -> None:
    """
    Show constitutional rule enforcement coverage.
    """
    core_context: CoreContext = ctx.obj
    file_handler = core_context.file_handler
    if not core_context.git_service or not file_handler:
        console.print(
            "[red]❌ Governance coverage requires CoreContext with git_service and file_handler.[/red]"
        )
        raise typer.Exit(code=1)

    repo_root = core_context.git_service.repo_path

    # 1. Gather Data (delegated to logic engine)
    coverage_data = logic.get_coverage_data(repo_root, file_handler)

    # 2. Handle JSON Output
    if format == "json":
        if output:
            rel_output = _to_rel_str(output, repo_root)
            file_handler.write_runtime_json(rel_output, coverage_data)
            console.print(f"[green]✅ Written to {output}[/green]")
        else:
            console.print_json(data=coverage_data)
        return

    # 3. Render Markdown and Print/Save
    content = (
        logic.render_hierarchical(coverage_data)
        if format == "hierarchical"
        else logic.render_summary(coverage_data)
    )

    if output:
        rel_output = _to_rel_str(output, repo_root)
        file_handler.write_runtime_text(rel_output, content)
        console.print(f"[green]✅ Written to {output}[/green]")
    else:
        console.print(content)


def _to_rel_str(path: Path, root: Path) -> str:
    """Converts a path to a repo-relative string."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
