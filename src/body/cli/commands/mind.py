# src/body/cli/commands/mind.py
"""
Registers the 'mind' command group for managing the Working Mind's SSOT.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import typer

from body.cli.logic.knowledge_sync import run_diff, run_import, run_snapshot, run_verify
from shared.cli_utils import core_command


mind_app = typer.Typer(
    help="Commands to manage the Working Mind (DB-as-SSOT).", no_args_is_help=True
)


@mind_app.command(
    "snapshot",
    help="Export the database to canonical YAML files in .intent/mind_export/.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 62323a98-f086-4657-ab80-8a90f77ec944
async def snapshot_command(
    ctx: typer.Context,
    env: str | None = typer.Option(
        None, "--env", help="Environment tag (e.g., 'dev', 'prod')."
    ),
    note: str | None = typer.Option(
        None, "--note", help="A brief note to store with the export manifest."
    ),
) -> None:
    """CLI wrapper for the snapshot logic."""
    await run_snapshot(env=env, note=note)


@mind_app.command(
    "diff", help="Compare the live database with the exported YAML files."
)
@core_command(dangerous=False, requires_context=False)
# ID: b49ec83d-b3a8-4337-8ce1-816df68b2e5e
async def diff_command(
    ctx: typer.Context,
    as_json: bool = typer.Option(
        False, "--json", help="Output the diff in machine-readable JSON format."
    ),
) -> None:
    """CLI wrapper for the diff logic."""
    await run_diff(as_json=as_json)


@mind_app.command(
    "import", help="Import the exported YAML files into the database (idempotent)."
)
@core_command(dangerous=True, confirmation=True)
# ID: c38fd5db-a945-47f6-bff2-f1ffee0ed6bd
async def import_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply the import to the database."
    ),
) -> None:
    """CLI wrapper for the import logic."""
    await run_import(dry_run=not write)


@mind_app.command(
    "verify", help="Recomputes digests for exported files and fails on mismatch."
)
@core_command(dangerous=False, requires_context=False)
# ID: f24f0d57-32ce-41b7-a0d4-d1d563054f94
def verify_command(ctx: typer.Context) -> None:
    """CLI wrapper for the verification logic."""
    if not run_verify():
        raise typer.Exit(code=1)


@mind_app.command(
    "validate-meta",
    help="Validate all .intent documents against GLOBAL-DOCUMENT-META-SCHEMA.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 78901abc-def2-3456-7890-abcdef234567
def validate_meta_command(ctx: typer.Context) -> None:
    """Validate .intent documents against META-SCHEMA."""
    from mind.governance.meta_validator import MetaValidator
    from shared.logger import getLogger

    logger = getLogger(__name__)

    logger.info("Validating .intent documents against META-SCHEMA...")

    validator = MetaValidator()
    report = validator.validate_all_documents()

    logger.info("\n📊 Validation Report:")
    logger.info(f"  Documents checked: {report.documents_checked}")
    logger.info(f"  Valid: {report.documents_valid}")
    logger.info(f"  Invalid: {report.documents_invalid}")

    if report.warnings:
        logger.warning(f"\n⚠️  Warnings ({len(report.warnings)}):")
        for warning in report.warnings:
            logger.warning(f"  {warning.document}: {warning.message}")

    if report.errors:
        logger.error(f"\n❌ Errors ({len(report.errors)}):")
        for error in report.errors:
            field_str = f" [{error.field}]" if error.field else ""
            logger.error(f"  {error.document}{field_str}: {error.message}")
        raise typer.Exit(1)

    logger.info("\n✅ All .intent documents valid")
