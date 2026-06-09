# src/mind/logic/engines/runtime_gate.py

"""
Runtime telemetry engine — consumes blackboard data, not source files.

Dispatches one check_type today:

- worker_process_classification (ADR-081 D7): aggregates loop_hold.sample
  blackboard entries (posted by Step 3a-telemetry) per worker stem,
  compares against .intent/workers/*.yaml's requires_dedicated_process
  declaration, and fires advisory findings:

  * escalation_required — a shares_process worker observed to monopolize
    the loop (max loop-hold > loop_hold_escalation_sec across the
    cycle_window). Proposes flipping the YAML to requires_dedicated_process:
    true.
  * deescalation_candidate — a requires_dedicated_process: true worker
    that observably stays quiet (max loop-hold < loop_hold_deescalation_sec
    across the cycle_window). Proposes governor review of whether the
    dedication is still warranted.

Skip-silently semantics on insufficient data: workers with fewer than
cycle_window samples post no finding either way. Right after a daemon
restart the rule reports clean until evidence accumulates; matches D7's
"5+ steady-state cycle window" requirement.

LAYER: mind.logic.engines — read-only verification. DB access via the
sanctioned async session. No file writes.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from sqlalchemy import text

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import BaseEngine, EngineResult


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


logger = getLogger(__name__)


_ENGINE_ID = "runtime_gate"
_CONTEXT_CHECK_TYPES = frozenset(
    {"worker_process_classification", "worker_max_interval_within_observed"}
)
_RULE_ID = "runtime.worker_process_classification"
_RULE_ID_MAX_INTERVAL = "runtime.worker_max_interval_within_observed"

# Issue #516 audit parameters. The 1.1 multiplier accommodates measurement
# jitter without papering over drift; the 10-sample minimum prevents
# warm-up-window alarms after daemon restart; the 24h window balances
# evidence sufficiency against tracking workload changes.
_MAX_INTERVAL_MULTIPLIER = 1.1
_MAX_INTERVAL_MIN_SAMPLES = 10
_MAX_INTERVAL_LOOKBACK_HOURS = 24


# ID: 9a8b7c6d-5e4f-3a2b-1c0d-9e8f7a6b5c4d
class RuntimeGateEngine(BaseEngine):
    """Runtime telemetry data engine (ADR-081 D7).

    Consumes blackboard data (not source files) to evaluate governance
    invariants that depend on observed runtime behaviour rather than
    static code structure. The first such check is the
    worker_process_classification drift detector — it fires on workers
    whose measured loop-hold contradicts their declared runtime profile.
    """

    engine_id = _ENGINE_ID

    @classmethod
    # ID: 1f2e3d4c-5b6a-7980-1234-5678abcdef01
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """All runtime_gate check_types dispatch context-level — they
        consume blackboard aggregations, not single files."""
        return check_type in _CONTEXT_CHECK_TYPES

    # ID: 2a3b4c5d-6e7f-8901-2345-67890abcdef0
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """runtime_gate is context-level only. Per-file dispatch is a
        contract violation; surface it clearly so a misconfigured mapping
        doesn't silently pass."""
        check_type = params.get("check_type", "<unknown>")
        return EngineResult(
            ok=False,
            message=f"runtime_gate.{check_type} is context-level only.",
            violations=[
                f"runtime_gate received per-file dispatch for check_type "
                f"'{check_type}'. Mapping must scope this rule context-level."
            ],
            engine_id=self.engine_id,
        )

    # ID: 3b4c5d6e-7f80-9012-3456-7890abcdef01
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Dispatch the registered context-level check_types."""
        check_type = params.get("check_type")
        if check_type == "worker_process_classification":
            return await _check_worker_process_classification(context)
        if check_type == "worker_max_interval_within_observed":
            return await _check_worker_max_interval_within_observed(context)
        return [
            AuditFinding(
                check_id=f"{self.engine_id}.{check_type or 'missing'}.error",
                severity=AuditSeverity.HIGH,
                message=(
                    f"runtime_gate.verify_context received unsupported "
                    f"check_type '{check_type}'."
                ),
                file_path="none",
            )
        ]


# ID: 4c5d6e7f-8091-0123-4567-890abcdef012
async def _check_worker_process_classification(
    context: AuditorContext,
) -> list[AuditFinding]:
    """ADR-081 D7 — drift detector implementation.

    For each active worker:
    1. Read its identity.uuid + implementation.requires_dedicated_process
       from .intent/workers/<stem>.yaml.
    2. Pull recent loop_hold.sample entries from the blackboard for that
       UUID.
    3. Skip if fewer than cycle_window samples (insufficient data).
    4. Compute max duration over the window.
    5. Fire escalation_required / deescalation_candidate per the gates.
    """
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )

    cfg = load_operational_config().worker_classification
    escalation_sec = cfg.loop_hold_escalation_sec
    deescalation_sec = cfg.loop_hold_deescalation_sec
    cycle_window = cfg.cycle_window

    # Build stem → declaration state map from .intent/workers/. Paused or
    # absent workers are skipped: nothing to evaluate for them.
    workers_dir = context.repo_path / ".intent" / "workers"
    workers_state: dict[str, dict[str, Any]] = {}
    for yaml_file in sorted(workers_dir.glob("*.yaml")):
        try:
            decl = yaml.safe_load(yaml_file.read_text()) or {}
        except Exception:
            continue
        if decl.get("metadata", {}).get("status") != "active":
            continue
        uuid_str = decl.get("identity", {}).get("uuid")
        if not uuid_str:
            continue
        workers_state[yaml_file.stem] = {
            "uuid": uuid_str,
            "is_dedicated": bool(
                decl.get("implementation", {}).get("requires_dedicated_process", False)
            ),
        }

    if not workers_state:
        return []

    # AuditorContext injects db_session for the duration of the audit run
    # (see filtered_audit.run_filtered_audit). The Mind layer must not
    # open sessions itself — architecture.boundary.database_session_access.
    session = getattr(context, "db_session", None)
    if session is None:
        logger.debug(
            "runtime_gate.worker_process_classification: db_session not "
            "injected — check deferred to next audit cycle."
        )
        return []

    findings: list[AuditFinding] = []
    for stem, state in workers_state.items():
        r = await session.execute(
            text(
                """
                SELECT payload->>'duration_sec' AS duration_sec
                FROM core.blackboard_entries
                WHERE subject = :subject
                  AND worker_uuid = cast(:worker_uuid as uuid)
                ORDER BY created_at DESC
                LIMIT :sample_cap
                """
            ),
            {
                "subject": f"loop_hold.sample::{stem}",
                "worker_uuid": state["uuid"],
                # Over-pull a little — some samples may have malformed
                # payloads we discard below; the cycle_window decision
                # is made on the parsed values.
                "sample_cap": cycle_window * 4,
            },
        )
        durations: list[float] = []
        for row in r:
            try:
                durations.append(float(row.duration_sec))
            except (TypeError, ValueError):
                continue

        # Skip-silently: not enough samples for D7's 5+ cycle window.
        # The rule reports clean for workers without sufficient evidence.
        if len(durations) < cycle_window:
            continue

        window = durations[:cycle_window]
        max_dur = max(window)
        p50_dur = statistics.median(window)

        if not state["is_dedicated"] and max_dur > escalation_sec:
            findings.append(
                AuditFinding(
                    # Per ADR-098 D4 / #606: parent rule
                    # runtime.worker_process_classification is advisory,
                    # which rule_executor maps to INFO at dispatch.
                    check_id=_RULE_ID,
                    severity=AuditSeverity.INFO,
                    message=(
                        f"escalation_required: worker '{stem}' declares "
                        f"requires_dedicated_process: false, but observed "
                        f"max loop-hold {max_dur:.2f}s over the last "
                        f"{cycle_window} samples (p50 {p50_dur:.2f}s; "
                        f"gate {escalation_sec:.1f}s). Per ADR-081 D7, "
                        f"flip implementation.requires_dedicated_process "
                        f"to true in .intent/workers/{stem}.yaml and "
                        f"enable core-daemon-worker@{stem}.service."
                    ),
                    file_path=f".intent/workers/{stem}.yaml",
                    context={
                        "verdict": "escalation_required",
                        "stem": stem,
                        "max_loop_hold_sec": max_dur,
                        "p50_loop_hold_sec": p50_dur,
                        "cycle_window": cycle_window,
                        "escalation_threshold_sec": escalation_sec,
                    },
                )
            )
        elif state["is_dedicated"] and max_dur < deescalation_sec:
            findings.append(
                AuditFinding(
                    check_id=_RULE_ID,
                    severity=AuditSeverity.INFO,
                    message=(
                        f"deescalation_candidate: worker '{stem}' "
                        f"declares requires_dedicated_process: true, but "
                        f"observed max loop-hold {max_dur:.2f}s over the "
                        f"last {cycle_window} samples (p50 {p50_dur:.2f}s; "
                        f"gate {deescalation_sec:.1f}s). Per ADR-081 D7, "
                        f"governor MAY review whether the dedication is "
                        f"still warranted; demoting could re-expose peers "
                        f"to contention this dedication was answering."
                    ),
                    file_path=f".intent/workers/{stem}.yaml",
                    context={
                        "verdict": "deescalation_candidate",
                        "stem": stem,
                        "max_loop_hold_sec": max_dur,
                        "p50_loop_hold_sec": p50_dur,
                        "cycle_window": cycle_window,
                        "deescalation_threshold_sec": deescalation_sec,
                    },
                )
            )

    return findings


# ID: 09fd7163-5c4b-4bcb-bf68-79357f7c66c5
async def _check_worker_max_interval_within_observed(
    context: AuditorContext,
) -> list[AuditFinding]:
    """Issue #516 — configured-vs-observed max_interval drift detector.

    For each active worker declared in .intent/workers/<stem>.yaml with a
    `schedule.max_interval` and an `identity.uuid`:

    1. Aggregate the last 24h of `worker.heartbeat` blackboard entries
       for that uuid via SQL window function (LAG over created_at).
    2. Skip silently if fewer than 10 inter-heartbeat samples are
       available — insufficient evidence to compare.
    3. Compute observed p95 inter-heartbeat gap from the SQL aggregation.
    4. Emit a reporting finding when p95 exceeds
       `max_interval x 1.1` — accommodates measurement jitter without
       papering over genuine drift.

    Each finding includes the configured value, the observed p95, the
    sample count, and a concrete bump suggestion so the operator can
    update the YAML in one read.
    """
    workers_dir = context.repo_path / ".intent" / "workers"
    if not workers_dir.is_dir():
        return []

    workers: dict[str, dict[str, Any]] = {}
    for yaml_file in sorted(workers_dir.glob("*.yaml")):
        try:
            decl = yaml.safe_load(yaml_file.read_text()) or {}
        except Exception:
            continue
        if decl.get("metadata", {}).get("status") != "active":
            continue
        uuid_str = decl.get("identity", {}).get("uuid")
        # schedule.max_interval is nested under `mandate.schedule` in the
        # worker schema (META/worker.schema.json) — not at top level.
        max_interval_raw = (
            decl.get("mandate", {}).get("schedule", {}).get("max_interval")
        )
        if not uuid_str or max_interval_raw is None:
            continue
        try:
            max_interval = int(max_interval_raw)
        except (TypeError, ValueError):
            continue
        if max_interval <= 0:
            continue
        workers[yaml_file.stem] = {
            "uuid": uuid_str,
            "max_interval": max_interval,
        }

    if not workers:
        return []

    session = getattr(context, "db_session", None)
    if session is None:
        logger.debug(
            "runtime_gate.worker_max_interval_within_observed: db_session "
            "not injected — check deferred to next audit cycle."
        )
        return []

    findings: list[AuditFinding] = []
    for stem, w in workers.items():
        # Window function over heartbeats: gap to previous heartbeat per
        # worker_uuid over the lookback window. PERCENTILE_CONT yields the
        # continuous p95 in seconds. COUNT excludes the first row (its
        # gap is NULL by definition).
        r = await session.execute(
            text(
                """
                WITH gaps AS (
                  SELECT
                    EXTRACT(
                      EPOCH FROM (
                        created_at - LAG(created_at) OVER (ORDER BY created_at)
                      )
                    ) AS gap
                  FROM core.blackboard_entries
                  WHERE subject = 'worker.heartbeat'
                    AND worker_uuid = cast(:worker_uuid as uuid)
                    AND created_at > NOW() - (:hours * INTERVAL '1 hour')
                )
                SELECT
                  COUNT(*) FILTER (WHERE gap IS NOT NULL) AS samples,
                  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gap) AS p95
                FROM gaps
                """
            ),
            {
                "worker_uuid": w["uuid"],
                "hours": _MAX_INTERVAL_LOOKBACK_HOURS,
            },
        )
        row = r.first()
        if row is None or row.samples is None:
            continue
        samples = int(row.samples)
        if samples < _MAX_INTERVAL_MIN_SAMPLES:
            continue
        if row.p95 is None:
            continue

        p95_gap = float(row.p95)
        threshold = w["max_interval"] * _MAX_INTERVAL_MULTIPLIER

        if p95_gap <= threshold:
            continue

        # Bump target: smallest integer comfortably above observed p95.
        # Round up to the next 60s to keep the YAML value tidy.
        suggested = int((p95_gap // 60 + 1) * 60)

        findings.append(
            AuditFinding(
                # Per ADR-098 D4 / #606: parent rule
                # runtime.worker_max_interval_within_observed is blocking,
                # which rule_executor maps to BLOCK at dispatch.
                check_id=_RULE_ID_MAX_INTERVAL,
                severity=AuditSeverity.BLOCK,
                message=(
                    f"worker '{stem}' configured max_interval="
                    f"{w['max_interval']}s but observed p95 cycle gap "
                    f"{p95_gap:.1f}s over the last {samples} heartbeats "
                    f"(threshold {threshold:.1f}s = configured x "
                    f"{_MAX_INTERVAL_MULTIPLIER}). Bump max_interval to "
                    f"≥{suggested}s in .intent/workers/{stem}.yaml or "
                    f"investigate why the worker's cycle has grown."
                ),
                file_path=f".intent/workers/{stem}.yaml",
                context={
                    "stem": stem,
                    "configured_max_interval_sec": w["max_interval"],
                    "observed_p95_gap_sec": round(p95_gap, 2),
                    "samples": samples,
                    "lookback_hours": _MAX_INTERVAL_LOOKBACK_HOURS,
                    "multiplier": _MAX_INTERVAL_MULTIPLIER,
                    "suggested_max_interval_sec": suggested,
                },
            )
        )

    return findings
