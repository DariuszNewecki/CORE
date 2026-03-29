# src/will/workers/worker_auditor.py
# ID: will.workers.worker_auditor
"""
WorkerAuditor - Worker Liveness Governance Worker.

Responsibility: Detect workers that have missed their declared heartbeat
schedule and post a finding to the Blackboard for each silent or abandoned
worker.

Constitutional standing:
- Declaration:      .intent/workers/worker_auditor.yaml
- Class:            governance
- Phase:            audit
- Permitted tools:  none — deterministic DB reads only
- Approval:         false — findings are observations only
- Schedule:         max_interval=120s, glide_off=12s (10% default)

Self-scheduling: WorkerAuditor manages its own asyncio loop via run_loop().
Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — governance worker. Reads worker_registry, reads
.intent/workers/ declarations for scheduled workers. Writes to Blackboard
only. No LLM. No file writes.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor
from shared.workers.base import Worker


logger = getLogger(__name__)

_FINDING_SUBJECT = "worker.silent"

# Default glide_off multiplier — 10% of max_interval
_GLIDE_OFF_MULTIPLIER = 0.10

# Fallback threshold (seconds) for workers with no schedule declaration
_FALLBACK_THRESHOLD = 600

# Strip non-ASCII characters that PostgreSQL SQL_ASCII encoding cannot store.
# Worker names from .intent/workers/ YAML titles may contain Unicode dashes or
# other decorative characters that cause UntranslatableCharacterError on insert.
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")


def _sanitize(value: str) -> str:
    """Replace non-ASCII characters with '?' for SQL_ASCII database safety."""
    if not isinstance(value, str):
        return str(value)
    return _NON_ASCII_RE.sub("?", value)


# ID: c3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a
class WorkerAuditor(Worker):
    """
    Governance worker. Reads worker_registry, computes per-worker liveness
    thresholds from .intent/ declarations, and posts a finding for each
    worker that has exceeded max_interval + glide_off since last heartbeat.

    Uses deduplication — does not re-post a finding for a worker already
    flagged as silent unless the previous finding is resolved.
    """

    declaration_name = "worker_auditor"

    def __init__(self) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 120)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * _GLIDE_OFF_MULTIPLIER), 10)
        )
        # Cache of per-worker thresholds loaded from .intent/
        self._thresholds: dict[str, int] = {}

    # -------------------------------------------------------------------------
    # Self-scheduling entry point — called once by Sanctuary
    # -------------------------------------------------------------------------

    # ID: d4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one audit cycle per
        max_interval seconds. Sanctuary calls this once on bootstrap.
        """
        logger.info(
            "WorkerAuditor: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("WorkerAuditor: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="worker_auditor.cycle_error",
                        payload={"error": _sanitize(str(exc))},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("WorkerAuditor: failed to post error report")

            await asyncio.sleep(self._max_interval)

    # -------------------------------------------------------------------------
    # Single audit cycle
    # -------------------------------------------------------------------------

    # ID: e5a6b7c8-d9e0-4f1a-2b3c-4d5e6f7a8b9c
    async def run(self) -> None:
        """
        Execute one liveness audit cycle:
        1. Post heartbeat
        2. Load per-worker schedules from .intent/
        3. Fetch registered workers from DB
        4. For each worker exceeding threshold: post finding (deduplicated)
        5. Post completion report
        """
        from body.services.service_registry import service_registry

        await self.post_heartbeat()

        self._thresholds = self._load_worker_thresholds()
        workers = await self._fetch_registered_workers(service_registry)
        existing = await self._fetch_existing_findings(service_registry)

        flagged = 0
        for worker in workers:
            # Sanitize worker_name — registry may contain non-ASCII characters
            # from YAML titles (e.g. em dashes). SQL_ASCII encoding rejects them.
            worker_name = _sanitize(worker["worker_name"])
            worker_uuid = str(worker["worker_uuid"])
            seconds_silent = worker["seconds_silent"]

            # Match against threshold using sanitized name (thresholds are also
            # loaded from YAML titles which are now sanitized in _load_worker_thresholds)
            threshold = self._thresholds.get(worker_name, _FALLBACK_THRESHOLD)

            if seconds_silent > threshold:
                subject = f"{_FINDING_SUBJECT}::{worker_uuid}"
                if subject in existing:
                    logger.debug(
                        "WorkerAuditor: %s already flagged, skipping.", worker_name
                    )
                    continue

                await self.post_finding(
                    subject=subject,
                    payload={
                        "worker_name": worker_name,
                        "worker_uuid": worker_uuid,
                        "seconds_silent": seconds_silent,
                        "threshold": threshold,
                        "status": worker["status"],
                    },
                )
                flagged += 1
                logger.warning(
                    "WorkerAuditor: %s silent for %ds (threshold=%ds)",
                    worker_name,
                    seconds_silent,
                    threshold,
                )

        await self.post_report(
            subject="worker_auditor.run.complete",
            payload={
                "workers_checked": len(workers),
                "flagged": flagged,
            },
        )
        logger.info(
            "WorkerAuditor: cycle complete — checked=%d flagged=%d",
            len(workers),
            flagged,
        )

    # -------------------------------------------------------------------------
    # Intent reading — load declared schedules per worker
    # -------------------------------------------------------------------------

    def _load_worker_thresholds(self) -> dict[str, int]:
        """
        Read all .intent/workers/*.yaml declarations and extract
        max_interval + glide_off per worker title.

        Returns mapping of worker_name (title) → threshold in seconds.
        Worker titles are sanitized to ASCII to match the sanitized names
        read from worker_registry during the audit cycle.
        Workers without schedule declaration use _FALLBACK_THRESHOLD.
        """
        thresholds: dict[str, int] = {}
        intent_workers = Path(".intent/workers")

        if not intent_workers.exists():
            return thresholds

        for yaml_path in intent_workers.glob("*.yaml"):
            try:
                data = strict_yaml_processor.load_strict(yaml_path)
                raw_title = data.get("metadata", {}).get("title", "")
                # Sanitize the title to match what will be in worker_registry
                # after re-registration with the fixed YAML files.
                title = _sanitize(raw_title)
                schedule = data.get("mandate", {}).get("schedule")
                if title and schedule:
                    max_interval = schedule.get("max_interval", _FALLBACK_THRESHOLD)
                    glide_off = schedule.get(
                        "glide_off",
                        max(int(max_interval * _GLIDE_OFF_MULTIPLIER), 10),
                    )
                    thresholds[title] = max_interval + glide_off
            except Exception as exc:
                logger.warning(
                    "WorkerAuditor: could not read %s: %s", yaml_path.name, exc
                )

        return thresholds

    # -------------------------------------------------------------------------
    # DB reads
    # -------------------------------------------------------------------------

    async def _fetch_registered_workers(self, registry: Any) -> list[dict[str, Any]]:
        """Return all active workers with seconds since last heartbeat."""
        svc = await registry.get_worker_registry_service()
        return await svc.fetch_registered_workers()

    async def _fetch_existing_findings(self, registry: Any) -> set[str]:
        """Return subjects of open worker.silent findings to avoid duplicates."""
        svc = await registry.get_blackboard_service()
        return await svc.fetch_open_finding_subjects_by_prefix(f"{_FINDING_SUBJECT}::%")
