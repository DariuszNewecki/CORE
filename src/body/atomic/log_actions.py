# src/body/atomic/log_actions.py
"""Atomic actions for LLM exchange log infrastructure maintenance (ADR-052).

CONSTITUTIONAL:
- Body layer — may import get_session directly (shared.infrastructure.database).
- No LLM calls. No file writes. Pure DDL.
- Registered actions route through ActionExecutor; never called directly.
"""

from __future__ import annotations

import re
import time
from datetime import date

from sqlalchemy import text

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

# ADR-052 partition-maintenance policy, now governor-tunable via
# operational_config.yaml log_maintenance (#774, ADR-040 sweep); these
# module constants are thin governed aliases, not literals.
_CFG = load_operational_config().log_maintenance
_ADVANCE_MONTHS: int = _CFG.advance_months
_DEFAULT_RETENTION_MONTHS: int = _CFG.default_retention_months
_TABLE = "core.llm_exchange_log"
_ARCHIVE_SCHEMA = "core_archive"
_PARTITION_RE = re.compile(r"^llm_exchange_log_(\d{4})_(\d{2})$")


# ID: 71f9da46-06a3-4efe-860c-f2c18ce3bcaf
def _next_months(n: int) -> list[tuple[int, int]]:
    """Return (year, month) tuples for the next n calendar months from today."""
    today = date.today()
    year, month = today.year, today.month
    result = []
    for i in range(1, n + 1):
        m = month + i
        y = year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        result.append((y, m))
    return result


# ID: 1b4d3b4e-6096-4ea1-887c-8d78c92e1e19
def _partition_ddl(year: int, month: int) -> str:
    """Build the idempotent CREATE TABLE ... PARTITION OF DDL for one month."""
    partition = f"{_TABLE}_{year:04d}_{month:02d}"
    start = f"{year:04d}-{month:02d}-01 00:00:00+00"
    if month == 12:
        end = f"{year + 1:04d}-01-01 00:00:00+00"
    else:
        end = f"{year:04d}-{month + 1:02d}-01 00:00:00+00"
    return (
        f"CREATE TABLE IF NOT EXISTS {partition} "
        f"PARTITION OF {_TABLE} "
        f"FOR VALUES FROM ('{start}') TO ('{end}')"
    )


@register_action(
    action_id="log.maintain_partitions",
    description="Create upcoming monthly partitions for core.llm_exchange_log (ADR-052)",
    category=ActionCategory.STATE,
    policies=[],
)
@atomic_action(
    action_id="log.maintain_partitions",
    intent="Ensure the next ADVANCE_MONTHS of llm_exchange_log partitions exist",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: f21cee4c-0482-4d17-ac0d-f145c33aba17
async def action_maintain_log_partitions(
    core_context: CoreContext,
    write: bool = False,
    advance_months: int = _ADVANCE_MONTHS,
    **kwargs,
) -> ActionResult:
    """Create the next advance_months monthly partitions for core.llm_exchange_log.

    Idempotent — CREATE TABLE IF NOT EXISTS is a no-op when the partition already
    exists. Dry-run (write=False) returns the planned DDL without executing it.
    ADR-052: partitions are never dropped by this action; archival is a separate job.
    """
    start = time.time()
    months = _next_months(advance_months)
    planned = [
        {"partition": f"{_TABLE}_{y:04d}_{m:02d}", "ddl": _partition_ddl(y, m)}
        for y, m in months
    ]

    if not write:
        return ActionResult(
            action_id="log.maintain_partitions",
            ok=True,
            data={
                "dry_run": True,
                "advance_months": advance_months,
                "planned": [p["partition"] for p in planned],
            },
            duration_sec=time.time() - start,
        )

    created: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    async with get_session() as session:
        for item in planned:
            partition_name = item["partition"]
            ddl = item["ddl"]
            try:
                # Check if the partition table already exists.
                exists_q = await session.execute(
                    text(
                        "SELECT 1 FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'core' "
                        "AND c.relname = :relname"
                    ),
                    {"relname": partition_name.split(".")[-1]},
                )
                if exists_q.first() is not None:
                    skipped.append(partition_name)
                    logger.debug(
                        "log.maintain_partitions: %s already exists — skipped",
                        partition_name,
                    )
                    continue
                await session.execute(text(ddl))
                await session.commit()
                created.append(partition_name)
                logger.info(
                    "log.maintain_partitions: created partition %s", partition_name
                )
            except Exception as exc:
                errors.append(f"{partition_name}: {exc}")
                logger.error(
                    "log.maintain_partitions: failed to create %s: %s",
                    partition_name,
                    exc,
                )

    ok = not errors
    return ActionResult(
        action_id="log.maintain_partitions",
        ok=ok,
        data={
            "dry_run": False,
            "advance_months": advance_months,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        },
        duration_sec=time.time() - start,
    )


# ID: d1c4e24b-e8f3-4575-8e40-f2c6f3fb4f79
def _cutoff_month(retention_months: int) -> tuple[int, int]:
    """Return (year, month) of the oldest month to keep in the active table.

    Partitions strictly older than (year, month) are candidates for archival.
    """
    today = date.today()
    total = today.year * 12 + (today.month - 1) - retention_months
    return (total // 12, total % 12 + 1)


# ID: 968e97de-d4c3-4024-b4fe-02dfc7ebb062
def _parse_partition_month(relname: str) -> tuple[int, int] | None:
    """Extract (year, month) from a partition relname like llm_exchange_log_2026_05."""
    m = _PARTITION_RE.match(relname)
    if m is None:
        return None
    return (int(m.group(1)), int(m.group(2)))


async def _read_retention_months_from_db() -> int:
    """Read log_retention_months from system_config; fall back to default.

    The column was added in ADR-052 — callers must tolerate its absence on older
    deployments until the live DB schema is updated.
    """
    try:
        async with get_session() as session:
            row = await session.execute(
                text("SELECT log_retention_months FROM core.system_config LIMIT 1")
            )
            result = row.fetchone()
            if result is not None:
                return int(result[0])
    except Exception as exc:
        logger.warning(
            "log.archive_partitions: could not read log_retention_months "
            "from system_config (%s) — using default %d",
            exc,
            _DEFAULT_RETENTION_MONTHS,
        )
    return _DEFAULT_RETENTION_MONTHS


@register_action(
    action_id="log.archive_partitions",
    description="Archive old llm_exchange_log partitions to core_archive schema (ADR-052 GxP retention)",
    category=ActionCategory.STATE,
    policies=[],
)
@atomic_action(
    action_id="log.archive_partitions",
    intent="Detach and move llm_exchange_log partitions older than retention_months to core_archive",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: 2a8f9806-0988-4971-a997-c481870bd82d
async def action_archive_log_partitions(
    core_context: CoreContext,
    write: bool = False,
    retention_months: int | None = None,
    **kwargs,
) -> ActionResult:
    """Archive llm_exchange_log partitions older than the retention window.

    retention_months: if None, reads from system_config.log_retention_months
    (default 24 when the column is absent). The Body layer owns this DB read.

    GxP variant (ADR-052): partitions are NEVER dropped — they are detached from
    the active table and moved to core_archive schema, where they remain queryable
    indefinitely for EU Annex 11 audit compliance.

    Dry-run (write=False) returns candidates without executing any DDL.
    """
    start = time.time()
    if retention_months is None:
        retention_months = await _read_retention_months_from_db()
    cutoff_year, cutoff_month = _cutoff_month(retention_months)

    async with get_session() as session:
        # Discover currently attached partitions via pg_catalog.
        rows = await session.execute(
            text(
                "SELECT c.relname "
                "FROM pg_inherits i "
                "JOIN pg_class c ON c.oid = i.inhrelid "
                "JOIN pg_class p ON p.oid = i.inhparent "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE p.relname = 'llm_exchange_log' "
                "  AND n.nspname = 'core' "
                "ORDER BY c.relname"
            )
        )
        attached = [row[0] for row in rows.fetchall()]

    candidates: list[str] = []
    for relname in attached:
        parsed = _parse_partition_month(relname)
        if parsed is None:
            continue
        p_year, p_month = parsed
        if (p_year, p_month) < (cutoff_year, cutoff_month):
            candidates.append(relname)

    if not write:
        return ActionResult(
            action_id="log.archive_partitions",
            ok=True,
            data={
                "dry_run": True,
                "retention_months": retention_months,
                "cutoff": f"{cutoff_year:04d}-{cutoff_month:02d}",
                "candidates": candidates,
                "candidate_count": len(candidates),
            },
            duration_sec=time.time() - start,
        )

    archived: list[str] = []
    errors: list[str] = []

    async with get_session() as session:
        # Ensure core_archive schema exists.
        await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_ARCHIVE_SCHEMA}"))
        await session.commit()

        for relname in candidates:
            qualified = f"core.{relname}"
            try:
                await session.execute(
                    text(f"ALTER TABLE {_TABLE} DETACH PARTITION {qualified}")
                )
                await session.execute(
                    text(f"ALTER TABLE {qualified} SET SCHEMA {_ARCHIVE_SCHEMA}")
                )
                await session.commit()
                archived.append(relname)
                logger.info(
                    "log.archive_partitions: moved %s to %s",
                    qualified,
                    _ARCHIVE_SCHEMA,
                )
            except Exception as exc:
                await session.rollback()
                errors.append(f"{relname}: {exc}")
                logger.error(
                    "log.archive_partitions: failed to archive %s: %s",
                    relname,
                    exc,
                )

    ok = not errors
    return ActionResult(
        action_id="log.archive_partitions",
        ok=ok,
        data={
            "dry_run": False,
            "retention_months": retention_months,
            "cutoff": f"{cutoff_year:04d}-{cutoff_month:02d}",
            "archived": archived,
            "errors": errors,
            "archived_count": len(archived),
            "error_count": len(errors),
        },
        duration_sec=time.time() - start,
    )
