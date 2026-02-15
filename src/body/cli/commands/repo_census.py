# src/body/cli/commands/inspect/repo_census.py
# ID: 58e27c7c-8e76-4a9b-a231-969800922c47

"""
CIM-0: Repository Structural Census command.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from body.services.cim import CensusService
from shared.cli_utils import core_command
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 5c5f81a2-257d-4f70-8190-99c1c5c335a1
def repo_census_cmd(
    ctx: typer.Context,
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root to inspect (default: current CORE repo)",
    ),
    out: Path = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory (default: var/cim/)",
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
    # Default to current CORE repo
    if path is None:
        path = settings.REPO_PATH
    else:
        path = path.resolve()

    if not path.exists():
        console.print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(1)

    if not path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {path}[/red]")
        raise typer.Exit(1)

    # Default output directory
    if out is None:
        out = settings.REPO_PATH / "var" / "cim"

    out.mkdir(parents=True, exist_ok=True)

    # Run census
    console.print(f"[blue]Running CIM-0 census on: {path}[/blue]")
    service = CensusService()
    census = service.run_census(path)

    # Write artifact
    output_file = out / "repo_census.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(
            census.model_dump(mode="json"),
            f,
            indent=2,
            ensure_ascii=False,
        )

    console.print(f"[green]✓ Census complete: {output_file}[/green]")
    console.print(f"  Files scanned: {census.tree.total_files}")
    console.print(f"  Execution surfaces: {len(census.execution_surfaces)}")
    console.print(f"  Mutation surfaces: {len(census.mutation_surfaces)}")
    if census.errors:
        console.print(f"  [yellow]Errors: {len(census.errors)}[/yellow]")
