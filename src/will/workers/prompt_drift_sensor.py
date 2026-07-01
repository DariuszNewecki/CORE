# src/will/workers/prompt_drift_sensor.py
# Constitutional compliance: Will-tier sensing worker. Inherits from Worker
# (shared/workers/base.py); blackboard posting routes through BlackboardPublisher.
# Baseline query routes through BlackboardQueryService (Body → allowed from Will).
# No direct DB import. No LLM calls. No file writes. ADR-134 D6.
"""
PromptDriftSensor — detects content changes in governed AI prompts.

Hashes system.txt (and user.txt when present) for every prompt listed in
governed_prompts.yaml, compares against a persisted baseline, and posts a
prompt.drift_detected finding for any prompt whose content changed since the
last cycle. The baseline is stored as a blackboard report so the sensor
survives daemon restarts without false-drift alerts.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: f837f009-1f3c-4c9c-a5a8-411f29fa9b6a
class PromptDriftSensor(Worker):
    """
    Sensing worker. Detects drift in governed prompt artifacts (ADR-134 D6).

    Governed prompts are listed in .intent/enforcement/config/governed_prompts.yaml.
    A drift event fires when the SHA-256 of system.txt (or user.txt) changes
    between cycles. The baseline is persisted on the blackboard so restarts
    do not cause spurious alerts.

    No LLM calls. No file writes. approval_required: false.
    """

    declaration_name = "prompt_drift_sensor"

    def __init__(self, core_context: Any = None) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 900)
        self._core_context = core_context

    # ID: 91c5734d-fa9c-415c-9a3d-97d25077913e
    async def run_loop(self) -> None:
        """Continuous self-scheduling loop. Sanctuary calls this once on bootstrap."""
        logger.info(
            "PromptDriftSensor: starting loop (max_interval=%ds)", self._max_interval
        )
        await self._register()

        while True:
            cycle_start = time.monotonic()
            try:
                await self.run()
            except Exception as exc:
                logger.error("PromptDriftSensor: cycle failed: %s", exc, exc_info=True)
            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(self._max_interval - elapsed, 0))

    # ID: 9a53bb07-a3f4-4611-878f-c527f338f8ec
    async def run(self) -> None:
        """
        Execute one drift-sensing cycle:
        1. Post heartbeat
        2. Load governed prompt list from .intent/
        3. Hash current content of each governed prompt
        4. Recover stored baseline from blackboard
        5. Post prompt.drift_detected findings for changed prompts
        6. Persist new baseline as a blackboard report
        """
        await self.post_heartbeat()

        governed = self._load_governed_prompts()
        if not governed:
            logger.warning(
                "PromptDriftSensor: governed_prompts.yaml is empty or missing."
            )
            await self.post_report(
                subject="prompt_drift_sensor.baseline",
                payload={"hashes": {}, "checked": 0, "drifted": []},
            )
            return

        current_hashes: dict[str, str] = {}
        for entry in governed:
            name = entry.get("name", "")
            if not name:
                continue
            h = self._compute_hash(name)
            if h is not None:
                current_hashes[name] = h

        baseline = await self._fetch_baseline()
        prior_hashes: dict[str, str] = baseline.get("hashes", {}) if baseline else {}

        drifted: list[str] = []
        for name, digest in current_hashes.items():
            if name in prior_hashes and prior_hashes[name] != digest:
                drifted.append(name)
                await self.post_finding(
                    subject=f"prompt::drift::{name}",
                    payload={
                        "prompt_name": name,
                        "previous_hash": prior_hashes[name],
                        "current_hash": digest,
                        "rule": "ai.prompt.governed_change_requires_review",
                    },
                    resolution_mechanism="human",
                )
                logger.info(
                    "PromptDriftSensor: drift detected in governed prompt '%s'.", name
                )

        await self.post_report(
            subject="prompt_drift_sensor.baseline",
            payload={
                "hashes": current_hashes,
                "checked": len(current_hashes),
                "drifted": drifted,
            },
        )

        if not drifted:
            logger.debug(
                "PromptDriftSensor: no drift in %d governed prompt(s).",
                len(current_hashes),
            )

    def _load_governed_prompts(self) -> list[dict[str, Any]]:
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        try:
            doc = get_intent_repository().load_policy(
                "enforcement/config/governed_prompts"
            )
            return doc.get("governed_prompts", [])
        except Exception as exc:
            logger.error(
                "PromptDriftSensor: could not load governed_prompts.yaml: %s", exc
            )
            return []

    def _compute_hash(self, prompt_name: str) -> str | None:
        """Return SHA-256 hex digest of system.txt + user.txt for *prompt_name*."""
        from shared.path_resolver import PathResolver

        prompt_dir: Path = (
            PathResolver(self._core_context.git_service.repo_path).prompts_dir
            / prompt_name
        )
        if not prompt_dir.is_dir():
            logger.warning(
                "PromptDriftSensor: prompt directory not found: %s", prompt_dir
            )
            return None

        h = hashlib.sha256()
        found_any = False
        for filename in ("system.txt", "user.txt"):
            candidate = prompt_dir / filename
            if candidate.is_file():
                h.update(filename.encode())
                h.update(candidate.read_bytes())
                found_any = True

        return h.hexdigest() if found_any else None

    async def _fetch_baseline(self) -> dict[str, Any] | None:
        from body.services.blackboard_service import BlackboardQueryService

        try:
            svc = BlackboardQueryService()
            return await svc.fetch_latest_report_payload("prompt_drift_sensor.baseline")
        except Exception as exc:
            logger.warning("PromptDriftSensor: could not fetch baseline: %s", exc)
            return None
