# src/body/atomic/log_actions.py
"""Atomic actions for LLM exchange log infrastructure maintenance (ADR-052).

CONSTITUTIONAL:
- Body layer — may import get_session directly (shared.infrastructure.database).
- No LLM calls. No file writes. Pure DDL.
- Registered actions route through ActionExecutor; never called directly.
"""

from __future__ import annotations

import time
from datetime import date

from sqlalchemy import text

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)

_ADVANCE_MONTHS: int = 3
_TABLE = "core.llm_exchange_log"


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
