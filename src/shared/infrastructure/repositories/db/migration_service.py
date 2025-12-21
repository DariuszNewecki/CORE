# src/shared/infrastructure/repositories/db/migration_service.py

"""
Provides the canonical, single-source-of-truth service for applying database schema migrations.
"""

from __future__ import annotations

import pathlib

import typer

from shared.logger import getLogger

from .common import (
    apply_sql_file,
    ensure_ledger,
    get_applied,
    load_policy,
    record_applied,
)


logger = getLogger(__name__)


async def _run_migrations(apply: bool):
    """The core async logic for running migrations."""
    try:
        pol = load_policy()
        migrations_config = pol.get("migrations", {})
        order = migrations_config.get("order", [])
        migration_dir = migrations_config.get("directory", "sql")
    except Exception as e:
        logger.error("Error loading database policy: %s", e)
        raise typer.Exit(code=1)

    await ensure_ledger()
    applied = await get_applied()
    pending = [m for m in order if m not in applied]

    if not pending:
        logger.info("DB schema is up to date.")
        return

    logger.warning("Pending migrations found: %s", pending)
    if not apply:
        logger.info("Run with '--apply' to execute them.")
        return

    for mig in pending:
        logger.info("Applying migration: %s", mig)
        try:
            await apply_sql_file(pathlib.Path(migration_dir) / mig)
            await record_applied(mig)
            logger.info("Migration %s applied successfully.", mig)
        except Exception as e:
            logger.error("FAILED to apply %s: %s", mig, e)
            raise typer.Exit(code=1)

    logger.info("All pending migrations applied successfully.")


# ID: 7bb0c5ee-480b-4d14-9147-853c9f9b25c5
async def migrate_db(
    apply: bool = typer.Option(False, "--apply", help="Apply pending migrations."),
):
    """Initialize DB schema and apply pending migrations."""
    await _run_migrations(apply)
