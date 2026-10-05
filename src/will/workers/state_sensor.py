# src/will/workers/state_sensor.py
# Constitutional compliance: Will-tier governance-class observer (state, not
# artifacts -- the observer_worker precedent). Inherits from
# ScheduledWorker (shared/workers); blackboard posting routes through
# BlackboardPublisher, queries and resolves through the Body BlackboardService,
# ledger writes through the Body StateLedgerService. git runs through the
# shared GitService. No LLM calls. No file writes. ADR-169 D1/D2/D3, ADR-030.
"""
StateSensor — CORE observes its own state every cycle (ADR-169).

Each cycle:

1. **Ledger (D1).** Observes HEAD, dirty paths, law of record vs law
   evaluated, and this daemon's loaded code identity, and appends the
   observation to core.state_observations (trigger ``cycle``) when it differs
   from the latest row — every change is history, an unchanged state adds no
   row.
2. **Law drift (D2).** One ``governance::law_drift::<path>`` finding per
   ``.intent/`` path that differs from HEAD (one ``(unknown)`` finding when the
   relation cannot be established). The finding names the path within one
   cycle of the edit, and resolves itself when the path matches HEAD again.
3. **Stale daemon (D3 / ADR-030).** ``governance::stale_daemon::core-daemon``
   while this process's loaded code differs from ``src/`` on disk (or that
   cannot be established). Acting workers suspend themselves meanwhile (the
   gate in shared.workers.base). If the finding is still open after
   ``daemon.stale_code_escalation_minutes``, a
   ``governance::stale_daemon_escalated::core-daemon`` finding is posted once.
   Both resolve themselves on the first cycle after a restart.

ADR-091 D2 Revision B resolution classification:
- Subject prefixes:     governance::law_drift::, governance::stale_daemon::,
                        governance::stale_daemon_escalated::
- resolution_mechanism: self_resolve
- Resolver path:        this sensor's run(): open findings whose condition did
                        not hold this cycle are resolved via
                        BlackboardService.resolve_entries.

Detection only for law drift (governor ruling 2026-10-05: work continues).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from shared.infrastructure.code_identity import code_drift, loaded_code_identity
from shared.infrastructure.intent.law_state import LawState
from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)

LAW_DRIFT_PREFIX = "governance::law_drift"
STALE_DAEMON_PREFIX = "governance::stale_daemon"
STALE_ESCALATED_PREFIX = "governance::stale_daemon_escalated"

# The process this sensor runs in. Dedicated --only processes carry their own
# gate (they suspend their acting worker and report it); the finding speaks
# for the main daemon, whose sensors make the condition visible.
_PROCESS = "core-daemon"
_FINDING_LIMIT = 500
_UNKNOWN_PATH = "(unknown)"


# ID: e40653a7-4cca-4943-98e8-c899a34def05
def law_drift_subjects(law: LawState) -> dict[str, str]:
    """{subject: path} for every law-drift finding this law state warrants."""
    if law.relationship == "MATCH":
        return {}
    if law.relationship == "UNKNOWN":
        return {f"{LAW_DRIFT_PREFIX}::{_UNKNOWN_PATH}": _UNKNOWN_PATH}
    paths = law.drift_paths or [".intent"]
    return {f"{LAW_DRIFT_PREFIX}::{path}": path for path in paths}


# ID: bc732ed2-e0f7-4210-b848-f9eac89c283a
def escalation_due(
    first_observed_at: str | None, window_minutes: int, now: datetime
) -> bool:
    """True when a stale-daemon finding has stayed open past the ADR-030 window.

    A finding without a readable timestamp is treated as due: an
    unattended-for-how-long that cannot be established must not suppress the
    escalation (governance.no_governance_bypass).
    """
    if not first_observed_at:
        return True
    try:
        observed = datetime.fromisoformat(first_observed_at)
    except ValueError:
        return True
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return now - observed >= timedelta(minutes=window_minutes)


# ID: 868f58d9-b940-4a5c-a679-6335f8425dc8
class StateSensor(ScheduledWorker):
    """Governance observer for ADR-169 D1/D2/D3: ledger, law drift, stale daemon."""

    declaration_name = "state_sensor"

    def __init__(self, core_context: Any = None) -> None:
        super().__init__()
        self._core_context = core_context

    # ID: 30417b61-efff-4ab4-b4ea-f536eae61b9d
    async def run(self) -> None:
        """One observation cycle: ledger, law drift, stale daemon, report."""
        from body.services.service_registry import service_registry
        from body.services.state_ledger_service import (
            StateLedgerService,
            observe_state,
        )
        from shared.path_resolver import PathResolver

        await self.post_heartbeat()

        repo_root = self._core_context.git_service.repo_path
        observation = observe_state(
            repo_root,
            PathResolver(repo_root).intent_root,
            "cycle",
            loaded_code_identity=loaded_code_identity(),
        )
        recorded = await StateLedgerService().record_if_changed(observation)

        blackboard = await service_registry.get_blackboard_service()
        law = observation.law_state
        law_open, law_posted, law_resolved = await self._sync_law_drift(blackboard, law)
        stale = await self._sync_stale_daemon(blackboard)

        await self.post_report(
            subject="state_sensor.run.complete",
            payload={
                "head_sha": observation.head_sha,
                "dirty_paths": len(observation.dirty_paths),
                "law_relationship": law.relationship,
                "law_drift_open": law_open,
                "law_drift_posted": law_posted,
                "law_drift_resolved": law_resolved,
                "ledger_row_appended": recorded,
                **stale,
            },
        )

    async def _open_findings(self, blackboard: Any, prefix: str) -> dict[str, Any]:
        """{subject: finding} for open findings under ``prefix::``."""
        rows = await blackboard.fetch_open_findings(
            prefix=f"{prefix}::%", limit=_FINDING_LIMIT
        )
        return {r["subject"]: r for r in rows}

    async def _sync_law_drift(
        self, blackboard: Any, law: LawState
    ) -> tuple[int, int, int]:
        """Post a finding per drifting path; resolve those that match again."""
        wanted = law_drift_subjects(law)
        existing = await self._open_findings(blackboard, LAW_DRIFT_PREFIX)
        head = (law.head_sha or "")[:12]

        posted = 0
        for subject, path in wanted.items():
            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "rule": "governance.law_drift",
                    "path": path,
                    "relationship": law.relationship,
                    "head_sha": law.head_sha,
                    "law_record_digest": law.record_digest,
                    "law_evaluated_digest": law.evaluated_digest,
                    "reason": law.reason,
                    "message": (
                        f"{path} differs from the law of record at {head}: CORE "
                        "is enforcing uncommitted law. Commit or revert it; "
                        "until then audit verdicts are DEGRADED, never PASS "
                        "(ADR-169 D2)."
                        if law.relationship == "DRIFT"
                        else "CORE cannot establish that the law it enforces is "
                        "the law of record; audit verdicts cannot be PASS "
                        "(ADR-169 D2)."
                    ),
                },
                resolution_mechanism="self_resolve",
            )
            posted += 1
            logger.warning("StateSensor: law drift -- %s (%s)", path, law.relationship)

        resolved = 0
        for subject, row in existing.items():
            if subject not in wanted:
                await blackboard.resolve_entries([row["id"]])
                resolved += 1
                logger.info("StateSensor: %s matches the law of record again", subject)
        return len(wanted), posted, resolved

    async def _sync_stale_daemon(self, blackboard: Any) -> dict[str, Any]:
        """ADR-030: post, escalate or resolve the stale-daemon findings."""
        drift = code_drift(use_cache=False)
        subject = f"{STALE_DAEMON_PREFIX}::{_PROCESS}"
        escalated_subject = f"{STALE_ESCALATED_PREFIX}::{_PROCESS}"
        existing = await self._open_findings(blackboard, STALE_DAEMON_PREFIX)
        escalated = await self._open_findings(blackboard, STALE_ESCALATED_PREFIX)

        if not drift.suspends_autonomy:
            resolved = 0
            for row in [*existing.values(), *escalated.values()]:
                await blackboard.resolve_entries([row["id"]])
                resolved += 1
            if resolved:
                logger.info(
                    "StateSensor: daemon runs the code on disk -- %d stale-daemon "
                    "finding(s) resolved",
                    resolved,
                )
            return {"code_state": drift.state, "stale_daemon_resolved": resolved}

        payload = {
            "rule": "governance.stale_daemon",
            "process": _PROCESS,
            "state": drift.state,
            "loaded_code_identity": drift.loaded_identity,
            "disk_code_identity": drift.disk_identity,
            "reason": drift.reason,
            "autonomous_execution": "suspended",
            "resolution": "restart the daemon (core-admin daemon restart)",
            "message": (
                "The daemon is running code that differs from src/ on disk. "
                "Autonomous execution is suspended until the governor restarts "
                "it (ADR-030)."
            ),
        }
        now = datetime.now(UTC)
        result: dict[str, Any] = {"code_state": drift.state}
        if subject not in existing:
            await self.post_finding(
                subject=subject,
                payload={**payload, "first_observed_at": now.isoformat()},
                resolution_mechanism="self_resolve",
            )
            result["stale_daemon_posted"] = True
            logger.warning(
                "StateSensor: stale daemon (%s) -- autonomous execution suspended "
                "until restart (ADR-030)",
                drift.state,
            )
            return result

        first_observed_at = existing[subject]["payload"].get("first_observed_at")
        if escalated_subject not in escalated and escalation_due(
            first_observed_at, self._escalation_minutes(), now
        ):
            await self.post_finding(
                subject=escalated_subject,
                payload={
                    **payload,
                    "first_observed_at": first_observed_at,
                    "escalated_at": now.isoformat(),
                    "priority": "elevated",
                },
                resolution_mechanism="self_resolve",
            )
            result["stale_daemon_escalated"] = True
            logger.warning(
                "StateSensor: stale daemon unattended since %s -- escalated (ADR-030)",
                first_observed_at,
            )
        return result

    def _escalation_minutes(self) -> int:
        from shared.infrastructure.intent.operational_config import (
            load_operational_config,
        )

        try:
            return int(load_operational_config().daemon.stale_code_escalation_minutes)
        except Exception as exc:
            logger.warning(
                "StateSensor: escalation window unreadable, using ADR-030 default: %s",
                exc,
            )
            return 30
