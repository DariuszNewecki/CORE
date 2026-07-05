# src/will/workers/prompt_drift_sensor.py
# Constitutional compliance: Will-tier sensing worker. Inherits from Worker
# (shared/workers/base.py); blackboard posting routes through BlackboardPublisher.
# Baseline query routes through BlackboardQueryService (Body → allowed from Will).
# No direct DB import. No LLM calls. No file writes. ADR-134 D6.
"""
PromptDriftSensor — detects content changes in governed AI prompts.

Hashes system.txt (and user.txt when present) for every prompt listed in
governed_prompts.yaml, compares against a persisted baseline, and posts a
prompt::drift::<name> finding for any prompt whose content changed since the
last cycle. The baseline is stored as a blackboard report so the sensor
survives daemon restarts without false-drift alerts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)


def _diff_file_hashes(prior: dict[str, str], current: dict[str, str]) -> list[str]:
    """Return filenames whose hash changed or that are new/removed."""
    all_keys = prior.keys() | current.keys()
    return [k for k in sorted(all_keys) if prior.get(k) != current.get(k)]


# ID: f837f009-1f3c-4c9c-a5a8-411f29fa9b6a
class PromptDriftSensor(ScheduledWorker):
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
        self._core_context = core_context

    # ID: 9a53bb07-a3f4-4611-878f-c527f338f8ec
    async def run(self) -> None:
        """
        Execute one drift-sensing cycle:
        1. Post heartbeat
        2. Load governed prompt list from .intent/
        3. Hash current content of each governed prompt (combined + per-file)
        4. Recover stored baseline from blackboard
        5. Post prompt::drift::<name> findings for changed prompts
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
                payload={"hashes": {}, "file_hashes": {}, "checked": 0, "drifted": []},
            )
            return

        anchors_by_name: dict[str, list[str]] = {
            entry["name"]: entry.get("anchors", [])
            for entry in governed
            if entry.get("name")
        }

        git_commit = self._get_current_commit()

        current_hashes: dict[str, str] = {}
        current_file_hashes: dict[str, dict[str, str]] = {}
        for name in anchors_by_name:
            combined, per_file = self._compute_hashes(name)
            if combined is not None:
                current_hashes[name] = combined
                current_file_hashes[name] = per_file

        baseline = await self._fetch_baseline()
        prior_hashes: dict[str, str] = baseline.get("hashes", {}) if baseline else {}
        prior_file_hashes: dict[str, dict[str, str]] = (
            baseline.get("file_hashes", {}) if baseline else {}
        )

        drifted: list[str] = []
        for name, digest in current_hashes.items():
            if name in prior_hashes and prior_hashes[name] != digest:
                drifted.append(name)
                changed_files = _diff_file_hashes(
                    prior_file_hashes.get(name, {}),
                    current_file_hashes.get(name, {}),
                )
                await self.post_finding(
                    subject=f"prompt::drift::{name}",
                    payload={
                        "prompt_name": name,
                        "adr_anchor": anchors_by_name.get(name, []),
                        "previous_hash": prior_hashes[name],
                        "current_hash": digest,
                        "changed_files": changed_files,
                        "git_commit": git_commit,
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
                "file_hashes": current_file_hashes,
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

    def _compute_hashes(self, prompt_name: str) -> tuple[str | None, dict[str, str]]:
        """Return (combined SHA-256, per-file SHA-256 map) for *prompt_name*.

        The combined hash covers system.txt, user.txt, and model.yaml (ADR-134)
        and is used for drift detection. The per-file map is stored in the
        baseline so that changed_files can be reported accurately on the next
        drift cycle.
        """
        from shared.path_resolver import PathResolver

        prompt_dir: Path = (
            PathResolver(self._core_context.git_service.repo_path).prompts_dir
            / prompt_name
        )
        if not prompt_dir.is_dir():
            logger.warning(
                "PromptDriftSensor: prompt directory not found: %s", prompt_dir
            )
            return None, {}

        combined = hashlib.sha256()
        per_file: dict[str, str] = {}
        for filename in ("system.txt", "user.txt", "model.yaml"):
            candidate = prompt_dir / filename
            if candidate.is_file():
                content = candidate.read_bytes()
                combined.update(filename.encode())
                combined.update(content)
                per_file[filename] = hashlib.sha256(content).hexdigest()

        if not per_file:
            return None, {}
        return combined.hexdigest(), per_file

    def _get_current_commit(self) -> str:
        """Return HEAD commit hash, or 'unknown' if git is unavailable."""
        try:
            return self._core_context.git_service.get_current_commit()
        except Exception:
            return "unknown"

    async def _fetch_baseline(self) -> dict[str, Any] | None:
        from body.services.blackboard_service import BlackboardQueryService

        try:
            svc = BlackboardQueryService()
            return await svc.fetch_latest_report_payload("prompt_drift_sensor.baseline")
        except Exception as exc:
            logger.warning("PromptDriftSensor: could not fetch baseline: %s", exc)
            return None
