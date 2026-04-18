# src/cli/resources/admin/validate_env.py
"""
Admin Validate-Env Command - Configuration Hardening.
Enforces the environment schema to prevent runtime connectivity failures.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from cli.utils import core_command
from shared.infrastructure.config_validator import ConfigValidator
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("validate-env")
@command_meta(
    canonical_name="admin.validate-env",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    summary="Validate that the environment configuration matches the required schema.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 412de56b-4db4-4e02-af43-53915b94e20e
def admin_validate_env_cmd(ctx: typer.Context) -> None:
    """
    Check .env for missing keys or invalid formats.
    Ensures the 'Body' has correct coordinates for its 'Nerves' (DB/Vectors).
    """
    validator = ConfigValidator()
    logger.info("\n[bold cyan]🛡️  Audit: Environment Schema Validation...[/bold cyan]\n")
    result = validator.validate_env()
    if result.ok:
        logger.info(
            "[bold green]✅ Environment Valid: All required configuration keys are present and correctly formatted.[/bold green]\n"
        )
    else:
        logger.info("[bold red]❌ Configuration Errors Detected:[/bold red]")
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Issue Description", style="yellow")
        for error in result.errors:
            table.add_row(error)
        logger.info(table)
        logger.info(
            "\n[dim]Please update your .env file and re-run this check.[/dim]\n"
        )
        raise typer.Exit(code=1)
