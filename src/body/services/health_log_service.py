# src/body/services/health_log_service.py
"""
HealthLogService - Data-access layer for system state reads and
core.system_health_log writes.

Covers:
  - ObserverWorker._collect_state (all four count queries)
  - ObserverWorker._write_health_log

F-19 backlog vector (#563, governor call 2026-06-13): the convergence goal is
re-anchored onto open-backlog *net trajectory*, evaluated as two components both
flat-or-declining — machine backlog (`open_findings`, the open + reaudit-queue
count) and governor-inbox backlog (`governor_inbox`, distinct `indeterminate` +
`resolution_mechanism='human'` subjects). `governor_inbox` is persisted into
`system_health_log.payload` beside `flow_24h` so its 30-day trajectory is
observable, not only the machine half ("persistence mirrors metric definition").
See `.specs/planning/CORE-Operational-Completeness.md` §2.2 note (6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from body.services.worker_registry_service import WorkerRegistryService
from shared.infrastructure.bootstrap_registry import bootstrap_registry
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.workers.schedule import load_worker_schedule_state


logger = getLogger(__name__)

_CFG = load_operational_config().health_log

# F-19 convergence CTE (#563). Single source of truth — also imported by
# `src/cli/resources/runtime/health.py` for the live dashboard panel so the
# persisted time series in `core.system_health_log.payload` and the live
# dashboard agree on counts.
#
# Counts are by DISTINCT subject, not row, so the per-cycle recycling firehose
# does not amplify flow. `abandoned` is split per memory
# `reference_blackboard_abandoned_two_semantics` (governor decision 2026-06-04,
# Option A on #563):
#   - Type A (sensor-by-design audit trail: worker.silent::*, worker.error,
#     *.cycle_error, *.scope_collision::*, loop_hold.sample::*,
#     coherence.violation_executor.blast_bound) folds into `resolved` as
#     resolved-by-policy.
#   - Type B (python::* audit-violation rows abandoned by violation_executor)
#     goes to `stuck` — the real "daemon cannot self-heal" signal.
#
# total_open counts `'open'` plus `'indeterminate'` with
# `resolution_mechanism = 'reaudit'` (post-ADR-091 D2 the reaudit queue lives in
# the `indeterminate` status + resolution_mechanism field, not the retired
# `'awaiting_reaudit'` status name).
F19_CONVERGENCE_SQL = """
WITH window_data AS (
    SELECT
        subject,
        MIN(created_at) AS first_seen,
        BOOL_OR(status = 'resolved' AND resolved_at >= :cutoff) AS resolved_in_window,
        BOOL_OR(status = 'abandoned' AND resolved_at >= :cutoff) AS abandoned_in_window,
        BOOL_OR(
            status = 'open'
            OR (status = 'indeterminate' AND resolution_mechanism = 'reaudit')
        ) AS is_open,
        MAX(CASE
            WHEN subject LIKE 'worker.silent::%' THEN 'type_a'
            WHEN subject = 'worker.error' THEN 'type_a'
            WHEN subject LIKE '%.cycle_error' THEN 'type_a'
            WHEN subject LIKE '%.scope_collision::%' THEN 'type_a'
            WHEN subject LIKE 'loop_hold.sample::%' THEN 'type_a'
            WHEN subject = 'coherence.violation_executor.blast_bound' THEN 'type_a'
            ELSE 'type_b'
        END) AS classification
    FROM core.blackboard_entries
    WHERE entry_type = 'finding'
    GROUP BY subject
)
SELECT
    COUNT(*) FILTER (WHERE first_seen >= :cutoff) AS created_24h,
    COUNT(*) FILTER (
        WHERE resolved_in_window
           OR (abandoned_in_window AND classification = 'type_a')
    ) AS resolved_24h,
    COUNT(*) FILTER (
        WHERE abandoned_in_window AND classification = 'type_b'
    ) AS stuck_24h,
    COUNT(*) FILTER (WHERE is_open) AS total_open
FROM window_data
"""

# F-19 governor-inbox backlog (#563). Single source of truth — the convergence
# operand persisted by ObserverWorker AND the live "Governor Inbox" dashboard
# panel (`cli/resources/runtime/health.py`) read this SAME predicate, so the two
# numbers cannot drift (mirrors the F19_CONVERGENCE_SQL single-source pattern).
# COUNT(DISTINCT subject): the governor acts on a subject, not each recycled row.
# `resolution_mechanism='human'` only: the reaudit queue is machine-handled and
# already folded into open_findings, so it is not the governor's inbox.
GOVERNOR_INBOX_SQL = """
SELECT
    COUNT(DISTINCT subject) AS governor_inbox,
    MIN(created_at) AS oldest_delegate
FROM core.blackboard_entries
WHERE entry_type = 'finding'
  AND status = 'indeterminate'
  AND resolution_mechanism = 'human'
"""


# ID: 1c26b39c-f6d2-4bee-a65c-bb24071ea25c
class HealthLogService:
    """
    Body layer service. Exposes system-state reads across
    core.blackboard_entries, core.worker_registry, and core.symbols,
    plus a write to core.system_health_log.
    All four read queries share a single session to match the
    original ObserverWorker._collect_state() semantics.
    """

    # ID: 1661aae5-c77e-4094-b057-4de80858bba9
    async def collect_system_state(
        self, stale_threshold_seconds: int = _CFG.stale_threshold_seconds
    ) -> dict[str, Any]:
        """
        Run all four system-state count queries in one session and return
        a state dict with keys: open_findings, stale_entries,
        silent_workers, orphaned_symbols.

        Covers:
          - ObserverWorker._collect_state
          - ObserverWorker._count_open_findings
          - ObserverWorker._count_stale_entries
          - ObserverWorker._count_silent_workers
          - ObserverWorker._count_orphaned_symbols
        """
        from datetime import UTC, datetime, timedelta

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            # F-19 (#563): "still-open work" is `'open'` plus `'indeterminate'`
            # with `resolution_mechanism = 'reaudit'` — the post-ADR-091 D2
            # reaudit queue. The retired `'awaiting_reaudit'` status name no
            # longer exists in the schema. COUNT(DISTINCT subject) so the
            # per-cycle row-recycling firehose does not amplify (#4).
            r = await session.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT subject) FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND (
                          status = 'open'
                          OR (status = 'indeterminate'
                              AND resolution_mechanism = 'reaudit')
                      )
                    """
                )
            )
            open_findings: int = r.scalar() or 0

            # F-19 governor-inbox backlog (#563, governor call 2026-06-13): the
            # second backlog component — work the daemon delegated to the human.
            # Reads GOVERNOR_INBOX_SQL, the single source the dashboard panel also
            # reads, so the persisted operand and the live "Governor Inbox" number
            # cannot drift.
            gi_row = (await session.execute(text(GOVERNOR_INBOX_SQL))).fetchone()
            governor_inbox: int = gi_row.governor_inbox if gi_row else 0

            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE (
                          status = 'open'
                          OR (status = 'indeterminate'
                              AND resolution_mechanism = 'reaudit')
                      )
                      AND created_at < now() - make_interval(secs => :threshold)
                    """
                ),
                {"threshold": stale_threshold_seconds},
            )
            stale_entries: int = r.scalar() or 0

            # F-19 flow rates (#563): persist `created_24h`, `resolved_24h`,
            # `stuck_24h`, `total_open` into the time series so the 30-day
            # sustained-window quality goal is observable from
            # `core.system_health_log.payload`, not only reconstructable from
            # the live dashboard.
            cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
            r = await session.execute(text(F19_CONVERGENCE_SQL), {"cutoff": cutoff_24h})
            row = r.fetchone()
            flow_24h: dict[str, int] = {
                "created": row.created_24h if row else 0,
                "resolved": row.resolved_24h if row else 0,
                "stuck": row.stuck_24h if row else 0,
                "total_open": row.total_open if row else 0,
            }

            # silent_workers per ADR-041 D2/D3: per-worker thresholds from
            # the shared schedule loader, plus orphan-skip. Same canonical
            # rule WorkerShopManager and the runtime dashboard apply.
            schedule_state = load_worker_schedule_state()
            registry_svc = WorkerRegistryService()
            silent_rows = await registry_svc.fetch_stale_workers_with_schedules(
                thresholds=schedule_state.thresholds,
                active_uuids=schedule_state.active_uuids,
                fallback_sec=schedule_state.fallback_sec,
            )
            silent_workers: int = len(silent_rows)

            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.symbols s1
                    WHERE s1.key IS NULL
                        AND s1.is_public = true
                        AND NOT EXISTS (
                        -- Check if any other symbol's 'calls' array contains this symbol's qualname
                        SELECT 1 FROM core.symbols s2
                        WHERE s2.calls @> to_jsonb(s1.qualname)
                        )
                    """
                )
            )
            orphaned_symbols: int = r.scalar() or 0

        return {
            "open_findings": open_findings,
            "governor_inbox": governor_inbox,
            "stale_entries": stale_entries,
            "silent_workers": silent_workers,
            "orphaned_symbols": orphaned_symbols,
            "flow_24h": flow_24h,
            "observed_at": datetime.now(UTC).isoformat(),
        }

    # ID: a32e06d3-3c7e-4724-b2b5-47f4b1eb1c92
    async def write_health_log(self, state: dict[str, Any]) -> None:
        """
        Append one row to core.system_health_log. Never updates existing rows.

        Covers:
          - ObserverWorker._write_health_log
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        INSERT INTO core.system_health_log
                            (open_findings, stale_entries, silent_workers,
                             orphaned_symbols, payload)
                        VALUES
                            (:open_findings, :stale_entries, :silent_workers,
                             :orphaned_symbols, cast(:payload as jsonb))
                        """
                    ),
                    {
                        "open_findings": state["open_findings"],
                        "stale_entries": state["stale_entries"],
                        "silent_workers": state["silent_workers"],
                        "orphaned_symbols": state["orphaned_symbols"],
                        "payload": json.dumps(
                            {
                                "flow_24h": state.get("flow_24h", {}),
                                "governor_inbox": state.get("governor_inbox", 0),
                            }
                        ),
                    },
                )
        self._append_convergence_artifact(state)

    # ID: e3a12f47-9c8b-4d5e-b6f0-2a3c8d9e0f1a
    def _append_convergence_artifact(self, state: dict[str, Any]) -> None:
        """Append one JSONL entry to var/reports/convergence.jsonl.

        Maintains a rolling window of _CFG.convergence_rolling_window entries
        so the file stays ~30 lines. Reads existing content with Path.read_text
        (reads are ungoverned); writes back via FileHandler (governed write
        surface). Fail-soft: any error is logged and swallowed so the artifact
        never disrupts the main health-log path.
        """
        from body.infrastructure.storage.file_handler import FileHandler

        entry = {
            "observed_at": state.get("observed_at"),
            "open_findings": state.get("open_findings", 0),
            "governor_inbox": state.get("governor_inbox", 0),
            "flow_24h": state.get("flow_24h", {}),
        }
        try:
            repo_root: Path = bootstrap_registry.get_repo_path()
            path_resolver = PathResolver.from_repo(
                repo_root=repo_root,
                intent_root=repo_root / ".intent",
            )
            artifact_path = path_resolver.reports_dir / "convergence.jsonl"
            rel_path = str(artifact_path.relative_to(repo_root))
            existing: list[str] = []
            if artifact_path.exists():
                existing = [
                    ln
                    for ln in artifact_path.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
            tail = existing[-(_CFG.convergence_rolling_window - 1) :]
            tail.append(json.dumps(entry))
            FileHandler(str(repo_root)).write_runtime_text(rel_path, "\n".join(tail))
        except Exception as err:
            logger.warning("Could not append convergence artifact: %s", err)
