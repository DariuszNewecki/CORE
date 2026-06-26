# src/shared/infrastructure/repositories/db/migration_service.py

"""
Provides the canonical, single-source-of-truth service for applying database schema migrations.
"""

from __future__ import annotations

import pathlib

from shared.exceptions import CoreError
from shared.logger import getLogger

from .common import (
    apply_sql_file,
    ensure_ledger,
    get_applied,
    load_policy,
    record_applied,
)


logger = getLogger(__name__)


# ID: 6cfacdf2-219d-44cf-baf9-bb11c8ea6834
class MigrationServiceError(CoreError):
    """Raised when database migration fails."""


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


# ID: e0c32b5c-a965-4ddb-ae96-f25a0e75ffdb
async def bootstrap_migrations() -> None:
    """Seed core._migrations for an existing install without re-running SQL.

    Use once on a database that already has all migrations applied manually
    (e.g. the current single-developer install). Records every entry in the
    manifest order list as applied so that future `migrate --apply` runs see
    a clean ledger and only execute genuinely new migrations.

    Safe to call multiple times — already-recorded entries are skipped.
    """
    try:
        pol = load_policy()
        migrations_config = pol.get("migrations", {})
        order = migrations_config.get("order", [])
    except Exception as e:
        logger.error("Error loading migration manifest: %s", e)
        raise MigrationServiceError(
            "Error loading migration manifest.", exit_code=1
        ) from e

    await ensure_ledger()
    applied = await get_applied()
    pending = [m for m in order if m not in applied]

    if not pending:
        logger.info("Bootstrap: ledger already complete, nothing to seed.")
        return

    for mig in pending:
        await record_applied(mig)
        logger.info("Bootstrap: recorded %s", mig)

    logger.info("Bootstrap complete: %d migration(s) seeded.", len(pending))
