# src/shared/infrastructure/repositories/db/migration_service.py

"""
Canonical service for inspecting and applying database schema migrations.

Orchestrates the manifest (``manifest``) and the atomic ledger engine
(``ledger_engine``, ADR-162 D7): each pending entry is applied in its own
transaction under the ledger's advisory lock, so a failure at entry N leaves
1..N-1 recorded and N fully rolled back, and re-running is safe by
construction. Only the ``write`` paths mutate anything; the defaults are
read-only (ADR-162 D1, ``cli.command.dangerous_marking``).

Two states are refused rather than repaired (fail closed):

* an **empty ledger on a populated schema** — the database was created from a
  historical ``schema.sql`` and never ledgered; the remedy is verified
  baseline adoption (:func:`adopt_baseline`, ADR-162 D3), never a blind seed;
* a **ledger/schema contradiction** — a recorded entry whose verify probe
  fails; the ledger claims a change the catalog does not show (the
  ``--bootstrap``-after-upgrade trap ADR-162 documents).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from shared.exceptions import CoreError
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .common import MigrationAssets, resolve_migration_assets
from .ledger_engine import (
    LedgerEngineError,
    MigrationOutcome,
    MigrationResult,
    SessionFactory,
    apply_migration,
    backfill_reconciled_markers,
    ensure_ledger,
    ledger_exists,
    read_applied,
    record_ledger_row,
    run_probe,
)
from .manifest import Baseline, Manifest, ManifestError, load_manifest


logger = getLogger(__name__)

# The object whose presence means "this database has a CORE schema" — the same
# gate the installer uses to decide that a schema is already present.
_SCHEMA_PRESENT_PROBE = "select to_regclass('core.blackboard_entries') is not null"


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
    markers_backfilled: list[str] = field(default_factory=list)

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


@dataclass
# ID: fb3e84ab-e25b-4f76-888e-ec0fdb220a8c
class LedgerInspection:
    """Read-only view of the ledger against the manifest and the catalog."""

    ledger_present: bool
    schema_present: bool
    applied: set[str]
    pending: list[str]
    probe_failures: list[str]  # recorded entries whose verify probe is false
    baseline_suggestion: str | None  # latest baseline whose probes all hold

    @property
    # ID: 73380acc-344f-4c8e-bc6a-035c492ebfd4
    def empty_ledger_on_populated_schema(self) -> bool:
        return self.schema_present and not self.applied


@dataclass
# ID: 53fe96ad-60eb-4f9f-9022-08e6885ca519
class AdoptionReport:
    """What ``adopt_baseline`` verified and (with ``write``) recorded."""

    tag: str
    through: str
    write: bool
    to_record: list[str]  # entries <= through not yet in the ledger
    recorded: list[str] = field(default_factory=list)


def _resolve_assets_or_raise() -> MigrationAssets:
    try:
        return resolve_migration_assets()
    except RuntimeError as exc:
        logger.error("Error locating migration assets: %s", exc)
        raise MigrationServiceError(str(exc), exit_code=1) from exc


def _load_manifest_or_raise(assets: MigrationAssets) -> Manifest:
    try:
        return load_manifest(assets=assets)
    except (ManifestError, OSError, RuntimeError, ValueError) as exc:
        logger.error("Error loading migration manifest: %s", exc)
        raise MigrationServiceError(
            f"Error loading migration manifest: {exc}", exit_code=1
        ) from exc


async def _probe_safely(session: AsyncSession, sql: str) -> bool:
    """A probe that errors (missing relation, missing column) is simply false."""
    try:
        async with session.begin_nested():
            return await run_probe(session, sql)
    except Exception as exc:  # any DB error means "does not hold"
        logger.debug("probe failed to evaluate (treated as false): %s", exc)
        return False


async def _baseline_holds(session: AsyncSession, baseline: Baseline) -> bool:
    for sql in baseline.probes:
        if not await _probe_safely(session, sql):
            return False
    return True


async def _suggest_baseline(session: AsyncSession, manifest: Manifest) -> str | None:
    """The LATEST declared baseline whose probes all hold, read-only."""
    for baseline in reversed(manifest.baselines):
        if await _baseline_holds(session, baseline):
            return baseline.tag
    return None


# ID: 93e2b17a-49a7-4c8e-9c97-638aa92cec1d
async def inspect_ledger(
    manifest: Manifest, *, session_factory: SessionFactory = get_session
) -> LedgerInspection:
    """Read-only: never creates the ledger or any other object (ADR-162 D2/D3)."""
    async with session_factory() as session:
        async with session.begin():
            present = await ledger_exists(session)
            applied = await read_applied(session) if present else set()
            schema_present = await _probe_safely(session, _SCHEMA_PRESENT_PROBE)
            failures = [
                e.id
                for e in manifest.entries
                if e.id in applied
                and e.verify is not None
                and not await _probe_safely(session, e.verify)
            ]
            suggestion = (
                await _suggest_baseline(session, manifest)
                if schema_present and not applied
                else None
            )
    pending = [m for m in manifest.order if m not in applied]
    return LedgerInspection(
        ledger_present=present,
        schema_present=schema_present,
        applied=applied,
        pending=pending,
        probe_failures=failures,
        baseline_suggestion=suggestion,
    )


def _refuse_unsafe_ledger(inspection: LedgerInspection) -> None:
    if inspection.empty_ledger_on_populated_schema:
        hint = (
            " `core-admin database migrate --adopt-baseline "
            f"{inspection.baseline_suggestion} --write`"
            if inspection.baseline_suggestion
            else " `core-admin database status` (no declared baseline matches this schema)"
        )
        raise MigrationServiceError(
            "Refused: the ledger is empty but the schema is populated — replaying "
            "history would fail or corrupt it. Adopt the verified baseline first:"
            + hint,
            exit_code=1,
        )
    if inspection.probe_failures:
        raise MigrationServiceError(
            "Refused: ledger/schema contradiction — recorded migration(s) whose "
            "verify probe fails: "
            + ", ".join(inspection.probe_failures)
            + ". The ledger claims changes the catalog does not show; resolve "
            "before migrating.",
            exit_code=1,
        )


# ID: 7bb0c5ee-480b-4d14-9147-853c9f9b25c5
async def migrate_db(
    write: bool = False,
    *,
    session_factory: SessionFactory = get_session,
    manifest: Manifest | None = None,
) -> MigrationReport:
    """List pending migrations; with ``write=True`` apply them one by one.

    Dry run (default) touches nothing — not even the ledger table. The write
    path refuses an empty ledger on a populated schema and any
    ledger/schema contradiction, creates a missing ledger (legacy shape; the
    ledger's own structure changes only through ledgered migrations) and
    applies each pending entry atomically in manifest order,
    stopping at the first failure with that entry unrecorded and rolled back
    (ADR-162 D7).
    """
    assets = _resolve_assets_or_raise()
    manifest = manifest or _load_manifest_or_raise(assets)

    inspection = await inspect_ledger(manifest, session_factory=session_factory)
    pending = inspection.pending
    report = MigrationReport(pending_before=pending, write=write)

    if not write:
        if pending:
            logger.warning("Pending migrations found: %s", pending)
            logger.info("Run with '--write' to execute them.")
        else:
            logger.info("DB schema is up to date.")
        return report

    _refuse_unsafe_ledger(inspection)
    if not pending:
        logger.info("DB schema is up to date.")
        return report

    await ensure_ledger(session_factory)
    for mig in pending:
        entry = manifest.entry(mig)
        logger.info("Applying migration: %s", mig)
        try:
            result = await apply_migration(
                entry,
                manifest.sql_path(mig, assets.root),
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

    unmarked = [
        r.id
        for r in report.results
        if r.outcome is MigrationOutcome.RECONCILED and not r.marker_recorded
    ]
    if unmarked:
        # Rows reconciled before 20260919_adr162_migrations_reconciled.sql ran
        # in this same pass: the column exists now, set their marker.
        report.markers_backfilled = await backfill_reconciled_markers(
            unmarked, session_factory=session_factory
        )
    logger.info(
        "Migrations complete: %d applied, %d reconciled, %d skipped.",
        len(report.applied),
        len(report.reconciled),
        len(report.skipped),
    )
    return report


# ID: 37f9dd56-7773-4dd7-8e48-940ea99b12f0
async def adopt_baseline(
    tag: str,
    *,
    write: bool = False,
    session_factory: SessionFactory = get_session,
    manifest: Manifest | None = None,
) -> AdoptionReport:
    """Verified baseline adoption (ADR-162 D3, R3-A).

    Records the manifest entries up to the declared baseline ``tag`` — only
    after **every** probe of that baseline holds, only when no *later*
    declared baseline also holds (ambiguity), and only when the ledger does
    not already record anything beyond the baseline. Naming a version is
    never sufficient on its own. Without ``write`` the same verification runs
    and the report says what would be recorded; nothing is written.
    """
    manifest = manifest or _load_manifest_or_raise(_resolve_assets_or_raise())
    try:
        baseline = manifest.baseline(tag)
    except KeyError:
        known = ", ".join(b.tag for b in manifest.baselines) or "(none)"
        raise MigrationServiceError(
            f"Refused: {tag!r} is not a declared baseline. Declared: {known}.",
            exit_code=1,
        ) from None

    through_idx = manifest.order.index(baseline.through)
    async with session_factory() as session:
        async with session.begin():
            for i, sql in enumerate(baseline.probes, start=1):
                if not await _probe_safely(session, sql):
                    raise MigrationServiceError(
                        f"Refused: baseline {tag} probe {i}/{len(baseline.probes)} "
                        f"does not hold — the database is not at {tag}. Nothing "
                        f"was recorded. Probe: {sql.strip()[:160]}",
                        exit_code=1,
                    )
            later = [
                b.tag
                for b in manifest.baselines
                if manifest.order.index(b.through) > through_idx
                and await _baseline_holds(session, b)
            ]
            if later:
                raise MigrationServiceError(
                    f"Refused: baseline {tag} holds but so does the later baseline "
                    f"{later[-1]} — adopting {tag} would leave already-present "
                    f"changes pending. Adopt {later[-1]} instead. Nothing was recorded.",
                    exit_code=1,
                )
            applied = (
                await read_applied(session) if await ledger_exists(session) else set()
            )

    beyond = [m for m in manifest.order[through_idx + 1 :] if m in applied]
    if beyond:
        raise MigrationServiceError(
            f"Refused: the ledger already records entries beyond baseline {tag}: "
            f"{', '.join(beyond[:3])}{'…' if len(beyond) > 3 else ''}. "
            "Nothing was recorded.",
            exit_code=1,
        )
    to_record = [m for m in manifest.order[: through_idx + 1] if m not in applied]
    report = AdoptionReport(
        tag=tag, through=baseline.through, write=write, to_record=to_record
    )
    if not write:
        logger.info(
            "Baseline %s verified: %d entries would be recorded (dry run).",
            tag,
            len(to_record),
        )
        return report

    await ensure_ledger(session_factory)
    for mig in to_record:
        if await record_ledger_row(
            mig, reconciled=False, session_factory=session_factory
        ):
            report.recorded.append(mig)
    logger.info(
        "Baseline %s adopted: %d ledger row(s) recorded through %s.",
        tag,
        len(report.recorded),
        baseline.through,
    )
    return report
