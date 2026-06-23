# src/cli/resources/constitution/validate.py
import typer
from rich.console import Console

from cli.utils import core_command
from mind.governance.meta_validator import MetaValidator
from mind.governance.specs_doc_validator import SpecsDocValidator

from . import app


console = Console()


@app.command("validate")
@core_command(dangerous=False, requires_context=False)
# ID: b75321ea-88dd-4ed1-93d8-b6730590777a
def validate_constitution(ctx: typer.Context) -> None:
    """
    Validate .intent/ artifacts and .specs/ document headers against their schemas.

    MetaValidator checks structural conformance of .intent/ YAML/JSON documents.
    SpecsDocValidator checks frontmatter headers on modeled .specs/ documents (ADR-105 D6).
    """
    console.print("[bold cyan]🛡️  Validating Constitutional Artifacts...[/bold cyan]\n")

    meta_validator = MetaValidator()
    meta_report = meta_validator.validate_all_documents()

    specs_validator = SpecsDocValidator()
    specs_report = specs_validator.validate_all_documents()

    all_valid = meta_report.valid and specs_report.valid

    if all_valid:
        total = meta_report.documents_valid + specs_report.documents_valid
        console.print(
            f"[green]✅ Success! {total} documents validated "
            f"({meta_report.documents_valid} intent, {specs_report.documents_valid} specs).[/green]"
        )
    else:
        total_errors = len(meta_report.errors) + len(specs_report.errors)
        console.print(
            f"[bold red]❌ Validation Failed: {total_errors} errors found.[/bold red]"
        )
        if meta_report.errors:
            console.print("[yellow].intent/ errors:[/yellow]")
            for err in meta_report.errors:
                console.print(f"   - [yellow]{err.document}[/yellow]: {err.message}")
        if specs_report.errors:
            console.print("[yellow].specs/ header errors:[/yellow]")
            for err in specs_report.errors:
                console.print(f"   - [yellow]{err.document}[/yellow]: {err.message}")
        raise typer.Exit(1)
