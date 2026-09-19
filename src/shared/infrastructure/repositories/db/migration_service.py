# src/shared/infrastructure/repositories/db/migration_service.py

"""
Canonical service for inspecting and applying database schema migrations.

Orchestrates the manifest (``manifest``) and the atomic ledger engine
(``ledger_engine``, ADR-162 D7): each pending entry is applied in its own
transaction under the ledger's advisory lock, so a failure at entry N leaves
1..N-1 recorded and N fully rolled back, and re-running is safe by
construction. Only the ``write`` path mutates anything; the default is a
read-only dry run (ADR-162 D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.exceptions import CoreError
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .common import REPO_ROOT
from .ledger_engine import (
    LedgerEngineError,
    MigrationOutcome,
    MigrationResult,
    SessionFactory,
    apply_migration,
    ensure_ledger,
    get_applied,
    record_ledger_row,
)
from .manifest import Manifest, ManifestError, load_manifest


logger = getLogger(__name__)


# ID: 6cfacdf2-219d-44cf-baf9-bb11c8ea6834
class MigrationServiceError(CoreError):
    """Raised when database migration fails."""


@dataclass
# ID: e9cc3a96-564f-4ec5-9eeb-29627dc9a76f
class MigrationReport:
    """What a ``migrate_db`` invocation found and did."""

    pending_before: list[str]
    write: bool
    results: list[MigrationResult] = field(default_factory=list)

    @property
    # ID: b04898b5-32f6-4b09-bd7d-3925882f2b88
    def applied(self) -> list[str]:
        return [r.id for r in self.results if r.outcome is MigrationOutcome.APPLIED]

    @property
    # ID: 910d1cdb-94b7-4d15-8e3e-525d9b0483ec
    def reconciled(self) -> list[str]:
        return [r.id for r in self.results if r.outcome is MigrationOutcome.RECONCILED]

    @property
    # ID: bfddd7af-c97c-42e6-a135-c2218770846d
    def skipped(self) -> list[str]:
        return [
            r.id for r in self.results if r.outcome is MigrationOutcome.SKIPPED_RECORDED
        ]


def _load_manifest_or_raise() -> Manifest:
    try:
        return load_manifest()
    except (ManifestError, OSError, RuntimeError, ValueError) as exc:
        logger.error("Error loading migration manifest: %s", exc)
        raise MigrationServiceError(
            f"Error loading migration manifest: {exc}", exit_code=1
        ) from exc


# ID: 7bb0c5ee-480b-4d14-9147-853c9f9b25c5
async def migrate_db(
    write: bool = False,
    *,
    session_factory: SessionFactory = get_session,
    manifest: Manifest | None = None,
) -> MigrationReport:
    """List pending migrations; with ``write=True`` apply them one by one.

    Dry run (default) touches nothing — not even the ledger table. The write
    path first brings the ledger to the engine's structure, then applies each
    pending entry atomically in manifest order and stops at the first failure,
    leaving that entry unrecorded and rolled back (ADR-162 D7).
    """
    manifest = manifest or _load_manifest_or_raise()
    if REPO_ROOT is None:
        raise MigrationServiceError(
            "Migration commands require the CORE source tree and cannot run "
            "from a pip-installed wheel.",
            exit_code=1,
        )

    if write:
        await ensure_ledger(session_factory)
    applied = await get_applied(session_factory)
    pending = [m for m in manifest.order if m not in applied]
    report = MigrationReport(pending_before=pending, write=write)

    if not pending:
        logger.info("DB schema is up to date.")
        return report

    logger.warning("Pending migrations found: %s", pending)
    if not write:
        logger.info("Run with '--write' to execute them.")
        return report

    for mig in pending:
        entry = manifest.entry(mig)
        logger.info("Applying migration: %s", mig)
        try:
            result = await apply_migration(
                entry,
                manifest.sql_path(mig, REPO_ROOT),
                session_factory=session_factory,
            )
        except LedgerEngineError as exc:
            logger.error("REFUSED %s: %s", mig, exc)
            raise MigrationServiceError(str(exc), exit_code=1) from exc
        except Exception as exc:
            logger.error("FAILED to apply %s: %s", mig, exc)
            raise MigrationServiceError(
                f"Failed to apply migration {mig}: {exc} (rolled back; not recorded)",
                exit_code=1,
            ) from exc
        report.results.append(result)
        logger.info("Migration %s: %s.", mig, result.outcome.value)

    logger.info(
        "Migrations complete: %d applied, %d reconciled, %d skipped.",
        len(report.applied),
        len(report.reconciled),
        len(report.skipped),
    )
    return report


# ID: e0c32b5c-a965-4ddb-ae96-f25a0e75ffdb
async def bootstrap_migrations(
    *, session_factory: SessionFactory = get_session
) -> list[str]:
    """Record every manifest entry as applied without running SQL.

    Unverified: it trusts the operator's claim that the database already
    carries every listed change. ADR-162 D3 retires it in favour of verified
    baseline adoption (``--adopt-baseline``, U4). Returns the ids recorded.
    """
    manifest = _load_manifest_or_raise()
    await ensure_ledger(session_factory)
    applied = await get_applied(session_factory)
    pending = [m for m in manifest.order if m not in applied]

    if not pending:
        logger.info("Bootstrap: ledger already complete, nothing to seed.")
        return []

    recorded: list[str] = []
    for mig in pending:
        if await record_ledger_row(
            mig, reconciled=False, session_factory=session_factory
        ):
            recorded.append(mig)
            logger.info("Bootstrap: recorded %s", mig)

    logger.info("Bootstrap complete: %d migration(s) seeded.", len(recorded))
    return recorded
