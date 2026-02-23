# src/body/cli/resources/constitution/validate.py
import typer
from rich.console import Console

from mind.governance.meta_validator import MetaValidator
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("validate")
@core_command(dangerous=False, requires_context=False)
# ID: 02013dc8-27d4-455e-98ca-b68dd1379d01
def validate_constitution(ctx: typer.Context) -> None:
    """
    Validate all .intent artifacts against their JSON schemas.

    Ensures that the Mind is structurally sound and follows the META-SCHEMA.
    """
    console.print("[bold cyan]🛡️  Validating Constitutional Artifacts...[/bold cyan]\n")

    validator = MetaValidator()
    report = validator.validate_all_documents()

    if report.valid:
        console.print(
            f"[green]✅ Success! {report.documents_valid} documents validated.[/green]"
        )
    else:
        console.print(
            f"[bold red]❌ Validation Failed: {len(report.errors)} errors found.[/bold red]"
        )
        for err in report.errors:
            console.print(f"   - [yellow]{err.document}[/yellow]: {err.message}")
        raise typer.Exit(1)
