# src/body/cli/commands/fix/apply_providers.py

"""
CLI command to apply automated provider refactoring.

Applies the refactoring changes for high-confidence cases identified by analysis.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from features.maintenance.apply_provider_refactoring import apply_provider_refactoring
from shared.cli_utils import core_command
from shared.config import settings

from . import fix_app


console = Console()


@fix_app.command("apply-providers")
@core_command(dangerous=True, confirmation=True)
# ID: e4f5a6b7-c8d9-0123-4567-890123defghi
# ID: a976110e-3f9f-46a9-9a42-0590ebf648ca
async def apply_provider_refactoring_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply changes (default is dry-run)"
    ),
    files: str = typer.Option(
        None,
        "--files",
        help="Comma-separated list of specific files to refactor (relative paths)",
    ),
) -> None:
    """
    Apply automated provider refactoring to 29 high-confidence files.

    This command refactors files identified by analyze-providers as high-confidence:
    - 12 files → IntentRepository pattern
    - 17 files → repo_path parameter pattern

    Changes made:
    - Removes direct settings imports
    - Adds IntentRepository or repo_path via dependency injection
    - Updates all settings.X usages to use providers

    IMPORTANT: Run 'fix analyze-providers' first to see what will change!
    """
    if not write:
        console.print("\n[yellow]⚠️  DRY RUN MODE[/yellow]")
        console.print("No changes will be made. Use --write to apply.\n")

    file_list = None
    if files:
        file_list = [f.strip() for f in files.split(",")]
        console.print(f"\n[cyan]Refactoring specific files:[/cyan] {len(file_list)}")
    else:
        console.print("\n[cyan]Refactoring all 29 high-confidence files[/cyan]\n")

    with console.status("[bold green]Applying refactorings..."):
        results = await apply_provider_refactoring(
            repo_path=settings.REPO_PATH,
            dry_run=not write,
            file_list=file_list,
        )

    # Display results
    console.print("\n[bold]Refactoring Results:[/bold]\n")

    # IntentRepository pattern
    ir_stats = results["intent_repository"]
    table1 = Table(title="IntentRepository Pattern")
    table1.add_column("Metric", style="cyan")
    table1.add_column("Count", justify="right", style="green")

    table1.add_row("Files attempted", str(ir_stats["attempted"]))
    table1.add_row("Successfully refactored", str(ir_stats["succeeded"]))
    if ir_stats["failed"] > 0:
        table1.add_row("Failed", str(ir_stats["failed"]), style="red")

    console.print(table1)

    # Show files
    if ir_stats["files"]:
        console.print("\n[dim]Files refactored with IntentRepository:[/dim]")
        for file_info in ir_stats["files"]:
            if file_info["success"]:
                console.print(
                    f"  ✅ {file_info['path']} ({file_info['changes']} changes)"
                )
            else:
                console.print(f"  ❌ {file_info['path']}")

    # repo_path parameter
    rp_stats = results["repo_path_param"]
    table2 = Table(title="\nRepo Path Parameter")
    table2.add_column("Metric", style="cyan")
    table2.add_column("Count", justify="right", style="green")

    table2.add_row("Files attempted", str(rp_stats["attempted"]))
    table2.add_row("Successfully refactored", str(rp_stats["succeeded"]))
    if rp_stats["failed"] > 0:
        table2.add_row("Failed", str(rp_stats["failed"]), style="red")

    console.print(table2)

    # Show files
    if rp_stats["files"]:
        console.print("\n[dim]Files refactored with repo_path parameter:[/dim]")
        for file_info in rp_stats["files"]:
            if file_info["success"]:
                console.print(
                    f"  ✅ {file_info['path']} ({file_info['changes']} changes)"
                )
            else:
                console.print(f"  ❌ {file_info['path']}")

    # Overall summary
    total_attempted = ir_stats["attempted"] + rp_stats["attempted"]
    total_succeeded = ir_stats["succeeded"] + rp_stats["succeeded"]
    total_failed = ir_stats["failed"] + rp_stats["failed"]

    console.print("\n[bold]Overall Summary:[/bold]")
    console.print(f"  Total files processed: {total_attempted}")
    console.print(f"  Successfully refactored: [green]{total_succeeded}[/green]")
    if total_failed > 0:
        console.print(f"  Failed: [red]{total_failed}[/red]")

    if not write:
        console.print("\n[yellow]DRY RUN - No files were modified[/yellow]")
        console.print("Review the changes above, then run with --write to apply.\n")
    else:
        console.print("\n[bold green]✅ Refactoring complete![/bold green]\n")
        console.print("[dim]Next steps:[/dim]")
        console.print("  1. Review the changes with git diff")
        console.print("  2. Run tests: pytest tests/")
        console.print("  3. Run constitutional audit: core-admin audit governance")
        console.print("  4. Update callers to pass IntentRepository/repo_path\n")
