# src/shared/infrastructure/repositories/db/migration_service.py

"""
Provides the canonical, single-source-of-truth service for applying database schema migrations.
"""

from __future__ import annotations

import pathlib

from shared.logger import getLogger

from .common import (
    apply_sql_file,
    ensure_ledger,
    get_applied,
    load_policy,
    record_applied,
)


logger = getLogger(__name__)


# ID: 0bbf5ba4-81da-449b-9503-9d6fd76212e5
class MigrationServiceError(RuntimeError):
    """Raised when migrations fail."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


async def _run_migrations(apply: bool):
    """The core async logic for running migrations."""
    try:
        pol = load_policy()
        migrations_config = pol.get("migrations", {})
        order = migrations_config.get("order", [])
        migration_dir = migrations_config.get("directory", "sql")
    except Exception as e:
        logger.error("Error loading database policy: %s", e)
        raise MigrationServiceError(
            "Error loading database policy.", exit_code=1
        ) from e

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
            raise MigrationServiceError(
                f"Failed to apply migration {mig}.", exit_code=1
            ) from e

    logger.info("All pending migrations applied successfully.")


# ID: 7bb0c5ee-480b-4d14-9147-853c9f9b25c5
async def migrate_db(apply: bool = False) -> None:
    """Initialize DB schema and apply pending migrations."""
    await _run_migrations(apply)
