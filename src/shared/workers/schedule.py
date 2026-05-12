# src/shared/workers/schedule.py
"""
WorkerScheduleState - single source of per-worker liveness inputs.

Per ADR-041 D4: the YAML-scanning logic that produces
``(thresholds, active_uuids)`` is centralised here so all readers
(WorkerShopManager, dashboard runtime health, health_log_service)
consume the same construction. This prevents drift at the YAML-reading
layer between the supervisor and downstream readers.

LAYER: shared/workers — pure function over .intent/workers/*.yaml,
routed through IntentRepository (the canonical gateway for .intent/).
No DB access, no file writes, no Worker dependency. Safe to import
from CLI, body services, and will/workers alike.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG = load_operational_config().workers.worker_shop


@dataclass(frozen=True)
# ID: f406d128-ea33-49d4-8095-9639089c6201
class WorkerScheduleState:
    """Per-worker liveness inputs derived from .intent/workers/*.yaml.

    thresholds: maps worker_uuid (string form) → max_interval + glide_off
                in seconds. Workers without a declared ``schedule`` block
                do not appear here; callers apply *fallback_sec* instead.

    active_uuids: the set of worker_uuids declared with ``status: active``.
                  Workers with any other status (paused, missing) are
                  absent. Callers use this for orphan-skip: registry rows
                  whose UUID is not in this set are excluded from
                  liveness reads (ADR-041 D3).

    fallback_sec: canonical liveness threshold for active workers that
                  declare no ``schedule`` block. Sourced from
                  ``operational_config.workers.worker_shop.fallback_threshold_sec``
                  so the producer (WorkerShopManager) and all readers
                  (dashboard, health_log_service) apply the same fallback.
    """

    thresholds: dict[str, int]
    active_uuids: frozenset[str]
    fallback_sec: int


# ID: f2d9b5b3-4a8e-4c7f-9d0a-2b3c4d5e6f7a
def load_worker_schedule_state(
    intent_repo: IntentRepository | None = None,
) -> WorkerScheduleState:
    """Read every declared worker via IntentRepository and return per-worker
    liveness inputs.

    Only YAMLs with ``metadata.status: active`` contribute. Workers with
    ``status: paused`` (or any other non-active status) yield neither
    a threshold nor an active-uuid entry — their registry rows, if
    present, are orphans by D3 and excluded from liveness reads.

    Failures reading individual worker declarations are logged and
    skipped; the function never raises on per-worker errors. A missing
    .intent/workers/ directory yields an empty state rather than an
    error.

    Per-worker threshold formula matches WorkerShopManager's pre-ADR-041
    computation: ``max_interval + glide_off`` from the worker's
    ``mandate.schedule`` block, with ``glide_off`` defaulting to
    ``max(max_interval * glide_off_multiplier, 10)`` from
    operational_config.

    The ``intent_repo`` parameter exists so callers on the hot path
    (WorkerShopManager runs this every cycle) and tests can pass a
    pre-constructed gateway and avoid repeating ``validate_intent_tree``.
    When omitted, the process-wide singleton from
    ``get_intent_repository()`` is used.
    """
    repo = intent_repo if intent_repo is not None else get_intent_repository()

    thresholds: dict[str, int] = {}
    active_uuids: set[str] = set()

    for worker_id in repo.list_workers():
        try:
            data = repo.load_worker(worker_id)
            if data.get("metadata", {}).get("status") != "active":
                continue
            uuid = (data.get("identity") or {}).get("uuid", "")
            if not uuid:
                continue
            active_uuids.add(uuid)
            schedule = data.get("mandate", {}).get("schedule")
            if schedule:
                max_interval = schedule.get("max_interval", _CFG.fallback_threshold_sec)
                glide_off = schedule.get(
                    "glide_off",
                    max(int(max_interval * _CFG.glide_off_multiplier), 10),
                )
                thresholds[uuid] = max_interval + glide_off
        except Exception as exc:
            logger.warning(
                "load_worker_schedule_state: could not read %s: %s",
                worker_id,
                exc,
            )

    return WorkerScheduleState(
        thresholds=thresholds,
        active_uuids=frozenset(active_uuids),
        fallback_sec=_CFG.fallback_threshold_sec,
    )
