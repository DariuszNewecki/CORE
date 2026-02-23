# src/body/cli/commands/mind.py

"""
Registers the 'mind' command group for managing the Working Mind's SSOT.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import typer

from shared.cli_utils import core_command


mind_app = typer.Typer(
    help="Commands to manage the Working Mind (DB-as-SSOT).", no_args_is_help=True
)


@mind_app.command(
    "validate-meta",
    help="Validate all .intent documents against GLOBAL-DOCUMENT-META-SCHEMA.",
)
@core_command(dangerous=False, requires_context=False)
# ID: eeca852a-b1d6-44c9-bb4f-5cadcd1307a9
def validate_meta_command(ctx: typer.Context) -> None:
    """Validate .intent documents against META-SCHEMA."""
    from mind.governance.meta_validator import MetaValidator
    from shared.logger import getLogger

    logger = getLogger(__name__)
    logger.info("Validating .intent documents against META-SCHEMA...")
    validator = MetaValidator()
    report = validator.validate_all_documents()
    logger.info("\n📊 Validation Report:")
    logger.info("  Documents checked: %s", report.documents_checked)
    logger.info("  Valid: %s", report.documents_valid)
    logger.info("  Invalid: %s", report.documents_invalid)
    if report.warnings:
        logger.warning("\n⚠️  Warnings (%s):", len(report.warnings))
        for warning in report.warnings:
            logger.warning("  %s: %s", warning.document, warning.message)
    if report.errors:
        logger.error("\n❌ Errors (%s):", len(report.errors))
        for error in report.errors:
            field_str = f" [{error.field}]" if error.field else ""
            logger.error("  %s%s: %s", error.document, field_str, error.message)
        raise typer.Exit(1)
    logger.info("\n✅ All .intent documents valid")
