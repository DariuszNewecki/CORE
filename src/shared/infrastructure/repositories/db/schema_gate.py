# src/shared/infrastructure/repositories/db/schema_gate.py
"""
Read-only startup schema gate (ADR-162 D2 / R2-A, U6).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — evaluates the
ledger against the manifest and the catalog and reports a verdict; it never
creates, alters or records anything, and it decides nothing about *what* to
migrate (the operator does, through ``core-admin database migrate``).

Before the API serves or the daemon starts workers, the gate evaluates the
database exactly as ``core-admin database status`` does and **refuses** —
exit 78, ``EX_CONFIG``, the code the ``core-engine`` entrypoint already uses —
when serving would run against a schema the code does not match:

* ``PENDING`` — known manifest entries are not recorded;
* ``EMPTY_LEDGER`` — a populated schema whose ledger records nothing (a
  database created from a historical ``schema.sql`` and never adopted);
* ``CONTRADICTION`` — a recorded entry whose verify probe fails (the ledger
  claims a change the catalog does not show);
* ``NO_SCHEMA`` — the database carries no CORE schema at all;
* ``ASSETS_UNAVAILABLE`` — the manifest cannot be read (precondition not
  evaluable → block, ``governance.no_governance_bypass``).

Every refusal names the exact remedy command. ``CORE_STRICT_MODE`` does not
relax any of this: a stale schema is deterministic breakage, not transient
infrastructure. A database that cannot be reached keeps the caller's existing
connectivity behaviour; the gate reports ``DB_UNAVAILABLE`` and does not
refuse on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .common import resolve_migration_assets
from .ledger_engine import SessionFactory
from .manifest import load_manifest
from .migration_service import inspect_ledger


logger = getLogger(__name__)

EX_CONFIG = 78


# ID: 90d0eb63-6cb0-4ad0-8ca3-c8873b9ab0aa
class SchemaGateState(str, Enum):
    CURRENT = "current"
    PENDING = "pending"
    EMPTY_LEDGER = "empty_ledger"
    CONTRADICTION = "contradiction"
    NO_SCHEMA = "no_schema"
    ASSETS_UNAVAILABLE = "assets_unavailable"
    DB_UNAVAILABLE = "db_unavailable"


_REFUSING = frozenset(
    {
        SchemaGateState.PENDING,
        SchemaGateState.EMPTY_LEDGER,
        SchemaGateState.CONTRADICTION,
        SchemaGateState.NO_SCHEMA,
        SchemaGateState.ASSETS_UNAVAILABLE,
    }
)


@dataclass(frozen=True)
# ID: c2114be2-842e-4fcb-8774-e72a4ca72e72
class SchemaGateVerdict:
    state: SchemaGateState
    message: str
    remedy: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    @property
    # ID: 7fbfe947-79a3-4574-972f-3fd4d18a0e57
    def refuses(self) -> bool:
        return self.state in _REFUSING


# ID: 28611b85-0041-4aea-a4dd-3611307469e6
class SchemaGateRefusal(RuntimeError):
    """Startup must not proceed; ``exit_code`` is EX_CONFIG (78)."""

    exit_code = EX_CONFIG

    def __init__(self, verdict: SchemaGateVerdict, component: str) -> None:
        self.verdict = verdict
        self.component = component
        remedy = f" Run: {verdict.remedy}" if verdict.remedy else ""
        super().__init__(f"{component} refused to start — {verdict.message}.{remedy}")


# ID: 775a8813-6247-44d2-b23c-129da4ea8dc3
async def evaluate_schema_gate(
    *, session_factory: SessionFactory = get_session
) -> SchemaGateVerdict:
    """Evaluate the database read-only and return the gate's verdict."""
    try:
        assets = resolve_migration_assets()
        manifest = load_manifest(assets=assets)
    except Exception as exc:  # manifest missing/unreadable/inconsistent
        return SchemaGateVerdict(
            SchemaGateState.ASSETS_UNAVAILABLE,
            f"migration assets unavailable: {exc}",
            remedy="reinstall core-runtime or restore infra/migrations/",
        )
    try:
        inspection = await inspect_ledger(manifest, session_factory=session_factory)
    except Exception as exc:  # connection refused, auth, DNS ...
        return SchemaGateVerdict(
            SchemaGateState.DB_UNAVAILABLE,
            f"database unavailable: {type(exc).__name__}",
            details={"error": str(exc)[:200]},
        )

    if not inspection.schema_present:
        return SchemaGateVerdict(
            SchemaGateState.NO_SCHEMA,
            "the database carries no CORE schema",
            remedy="load schema.sql (fresh install: ./install-core.sh)",
        )
    if inspection.empty_ledger_on_populated_schema:
        tag = inspection.baseline_suggestion
        remedy = (
            f"core-admin database migrate --adopt-baseline {tag} --write, "
            "then core-admin database migrate --write"
            if tag
            else "core-admin database status (no declared baseline matches this schema)"
        )
        return SchemaGateVerdict(
            SchemaGateState.EMPTY_LEDGER,
            "ledger not initialised on a populated schema",
            remedy=remedy,
            details={"baseline_suggestion": tag},
        )
    if inspection.probe_failures:
        first = inspection.probe_failures[0]
        return SchemaGateVerdict(
            SchemaGateState.CONTRADICTION,
            f"ledger/schema contradiction: {len(inspection.probe_failures)} recorded "
            f"migration(s) whose probe fails (first: {first})",
            remedy="core-admin database status",
            details={"probe_failures": list(inspection.probe_failures)},
        )
    if inspection.pending:
        return SchemaGateVerdict(
            SchemaGateState.PENDING,
            f"schema pending: {len(inspection.pending)} migration(s) "
            f"(first: {inspection.pending[0]})",
            remedy="core-admin database migrate --write",
            details={"pending": list(inspection.pending), "assets": assets.origin},
        )
    return SchemaGateVerdict(
        SchemaGateState.CURRENT,
        f"schema current ({len(inspection.applied)} migrations recorded, "
        f"assets: {assets.origin})",
    )


# ID: 3aacbc72-d0f6-4225-91fc-2eda46ab0171
async def run_startup_schema_gate(
    component: str, *, session_factory: SessionFactory = get_session
) -> SchemaGateVerdict:
    """Evaluate and enforce the gate for ``component`` ("CORE API", "CORE daemon").

    Raises :class:`SchemaGateRefusal` (exit 78) on every refusing state,
    regardless of ``CORE_STRICT_MODE``. Returns the verdict for ``CURRENT``
    and for ``DB_UNAVAILABLE`` (the caller's own connectivity handling
    applies to the latter).
    """
    verdict = await evaluate_schema_gate(session_factory=session_factory)
    if verdict.refuses:
        logger.critical(
            "❌ %s refused to start — %s. Run: %s",
            component,
            verdict.message,
            verdict.remedy or "core-admin database status",
        )
        raise SchemaGateRefusal(verdict, component)
    if verdict.state is SchemaGateState.DB_UNAVAILABLE:
        logger.warning("Schema gate could not evaluate: %s", verdict.message)
    else:
        logger.info("✅ Schema gate: %s", verdict.message)
    return verdict
