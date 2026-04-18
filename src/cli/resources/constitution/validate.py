# src/cli/resources/constitution/validate.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from mind.governance.meta_validator import MetaValidator

from . import app


console = Console()


@app.command("validate")
@core_command(dangerous=False, requires_context=False)
# ID: b75321ea-88dd-4ed1-93d8-b6730590777a
def validate_constitution(ctx: typer.Context) -> None:
    """
    Validate all .intent artifacts against their JSON schemas.

    Ensures that the Mind is structurally sound and follows the META-SCHEMA.
    """
    logger.info("[bold cyan]🛡️  Validating Constitutional Artifacts...[/bold cyan]\n")
    validator = MetaValidator()
    report = validator.validate_all_documents()
    if report.valid:
        logger.info(
            "[green]✅ Success! %s documents validated.[/green]", report.documents_valid
        )
    else:
        logger.info(
            "[bold red]❌ Validation Failed: %s errors found.[/bold red]",
            len(report.errors),
        )
        for err in report.errors:
            logger.info("   - [yellow]%s[/yellow]: %s", err.document, err.message)
        raise typer.Exit(1)
