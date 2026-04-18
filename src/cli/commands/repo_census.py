# src/cli/commands/repo_census.py
"""
CIM-0: Repository Structural Census command.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from body.services.cim import CensusService
from cli.utils import core_command
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext
logger = getLogger(__name__)
console = Console()


@core_command(dangerous=False, requires_context=True)
# ID: 1440f47b-17e3-4b9f-bd26-332da3631636
def repo_census_cmd(
    ctx: typer.Context,
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root to inspect (default: current CORE repo)",
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Output directory (default: var/cim/)"
    ),
) -> None:
    """
    CIM-0: Perform a mechanical census of a repository.

    Produces a deterministic JSON artifact describing:
    - File tree statistics
    - Architectural signals (src/, .intent/, etc.)
    - Execution surfaces (CLI entrypoints, __main__ blocks)
    - Mutation surfaces (filesystem, subprocess, network, database)

    This is a READ-ONLY operation that never modifies the target.
    """
    context: CoreContext = ctx.obj
    if path is None:
        path = context.git_service.repo_path
    else:
        path = path.resolve()
    if not path.exists():
        logger.info("[red]Error: Path does not exist: %s[/red]", path)
        raise typer.Exit(1)
    if not path.is_dir():
        logger.info("[red]Error: Path is not a directory: %s[/red]", path)
        raise typer.Exit(1)
    if out is None:
        out = context.git_service.repo_path / "var" / "cim"
    out.mkdir(parents=True, exist_ok=True)
    logger.info("[blue]Running CIM-0 census on: %s[/blue]", path)
    service = CensusService()
    census = service.run_census(path)
    output_file = out / "repo_census.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(census.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    logger.info("[green]✓ Census complete: %s[/green]", output_file)
    logger.info("  Files scanned: %s", census.tree.total_files)
    logger.info("  Execution surfaces: %s", len(census.execution_surfaces))
    logger.info("  Mutation surfaces: %s", len(census.mutation_surfaces))
    if census.errors:
        logger.info("  [yellow]Errors: %s[/yellow]", len(census.errors))
