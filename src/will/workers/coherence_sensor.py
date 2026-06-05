# src/will/workers/coherence_sensor.py
"""
CoherenceSensorWorker — sensor-fixer incoherence detection (ADR-027).

Joins core.proposal_consequences against core.blackboard_entries to find
proposals that resolved a (check_id, file_path) finding but where a new
finding for the same (check_id, file_path) appeared after the proposal
recorded its consequence — i.e. the fixer ran "successfully" yet the
sensor re-detected the violation. Posts a deduplicated
`python::coherence.incoherence::<check_id>::<file_hash>` finding per
occurrence (ADR-091 D2 canonical subject format).

Constitutional standing:
- Declaration:      .intent/workers/coherence_sensor.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none — deterministic DB reads only
- Approval:         false — findings are observations only
- Schedule:         max_interval=600s

LAYER: will/workers — sensing worker. Reads core.proposal_consequences
and core.blackboard_entries via service_registry.session(). Reads the
coherence_lookback_seconds threshold from .intent/cim/thresholds.yaml.
Writes to Blackboard only. No LLM. No file writes.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor
from shared.workers.base import Worker


logger = getLogger(__name__)

_THRESHOLDS_PATH = Path(".intent/cim/thresholds.yaml")
_LOOKBACK_KEY = "coherence_lookback_seconds"
_CFG = load_operational_config().workers.coherence_sensor

_INCOHERENCE_QUERY = text(
    """
    SELECT DISTINCT
        pc.proposal_id,
        f_old.payload->>'check_id'   AS check_id,
        f_old.payload->>'file_path'  AS file_path,
        f_new.id::text               AS new_finding_id
    FROM core.proposal_consequences pc
    CROSS JOIN LATERAL
        jsonb_array_elements_text(pc.findings_resolved) AS fr(finding_id)
    JOIN core.blackboard_entries f_old
        ON f_old.id::text = fr.finding_id
    JOIN core.blackboard_entries f_new
        ON  f_new.payload->>'check_id'  = f_old.payload->>'check_id'
        AND f_new.payload->>'file_path' = f_old.payload->>'file_path'
        AND f_new.entry_type  = 'finding'
        AND f_new.created_at  > pc.recorded_at
        AND f_new.id          != f_old.id
        AND f_new.status NOT IN (
            'resolved',
            'abandoned',
            'suppressed',
            'dry_run_complete',
            'deferred_to_proposal',
            'indeterminate'
        )
    WHERE pc.recorded_at > NOW() - (:lookback * INTERVAL '1 second')
      AND pc.findings_resolved IS NOT NULL
      AND jsonb_array_length(pc.findings_resolved) > 0
      AND f_old.payload->>'check_id'  IS NOT NULL
      AND f_old.payload->>'file_path' IS NOT NULL
    """
)


# ID: e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b
class CoherenceSensorWorker(Worker):
    """
    Sensing worker. Detects sensor-fixer incoherence per ADR-027:
    a proposal whose execution recorded findings_resolved for some
    (check_id, file_path) yet a fresh open finding for the same pair
    exists in core.blackboard_entries with created_at after the
    consequence was recorded. Posts one
    `python::coherence.incoherence::<check_id>::<file_hash>` finding per
    occurrence (ADR-091 D2); deduplicates against open coherence findings
    so a single ongoing incoherence does not flood the blackboard.

    Detection only — does not modify proposals or findings.
    """

    declaration_name = ""

    def __init__(self, **kwargs: Any) -> None:
        # Forward only declaration_name to super; ignore other daemon
        # kwargs (e.g. cognitive_service) that this worker does not use.
        super().__init__(declaration_name=kwargs.get("declaration_name", ""))

        # ADR-091 D1: artifact_type + rule_namespace required on class:sensing.
        # Subject construction routes through the declared values per D2's
        # canonical `<artifact_type>::<rule_namespace>::<identity_key>` shape.
        scope = self._declaration["mandate"]["scope"]
        self._artifact_type: str = scope["artifact_type"][0]
        self._rule_namespace: str = scope["rule_namespace"]

    # ID: a2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6d
    async def run(self) -> None:
        """
        One detection cycle: load lookback threshold, query for incoherent
        (proposal, check_id, file_path) tuples, post a deduplicated
        `python::coherence.incoherence` finding per row (ADR-091 D2).

        The heartbeat is posted unconditionally before any DB work so a
        downstream failure does not cause the supervisor to flag this
        worker as silent.
        """
        await self.post_heartbeat()

        try:
            from body.services.service_registry import service_registry

            lookback_seconds = self._load_lookback_seconds()

            blackboard_service = await service_registry.get_blackboard_service()
            existing = await blackboard_service.fetch_open_finding_subjects_by_prefix(
                f"{self._artifact_type}::{self._rule_namespace}::%"
            )

            checked = 0
            posted = 0

            async with service_registry.session() as session:
                result = await session.execute(
                    _INCOHERENCE_QUERY, {"lookback": lookback_seconds}
                )
                rows = result.fetchall()

            for row in rows:
                checked += 1
                proposal_id = row[0]
                check_id = row[1]
                file_path = row[2]
                new_finding_id = row[3]

                file_hash = hashlib.md5(
                    file_path.encode("utf-8"), usedforsecurity=False
                ).hexdigest()[:8]
                identity_key_value = f"{check_id}::{file_hash}"
                subject = f"{self._artifact_type}::{self._rule_namespace}::{identity_key_value}"

                if subject in existing:
                    logger.debug(
                        "CoherenceSensorWorker: %s already open, skipping.",
                        subject,
                    )
                    continue

                await self.post_artifact_finding(
                    artifact_type=self._artifact_type,
                    sub_namespace=self._rule_namespace,
                    identity_key_value=identity_key_value,
                    payload={
                        "check_id": check_id,
                        "file_path": file_path,
                        "proposal_id": str(proposal_id),
                        "re_posted_finding_id": new_finding_id,
                        "detected_at": datetime.now(UTC).isoformat(),
                    },
                )
                posted += 1
                logger.warning(
                    "CoherenceSensorWorker: incoherence — proposal=%s "
                    "check_id=%s file_path=%s re_posted_finding_id=%s",
                    proposal_id,
                    check_id,
                    file_path,
                    new_finding_id,
                )

            await self.post_report(
                subject="coherence_sensor.run.complete",
                payload={
                    "checked": checked,
                    "incoherent": posted,
                },
            )
            logger.info(
                "CoherenceSensorWorker: cycle complete — checked=%d incoherent=%d",
                checked,
                posted,
            )
        except Exception as exc:
            logger.error("CoherenceSensorWorker: cycle failed: %s", exc, exc_info=True)

    # ID: b3c4d5e6-f7a8-4b9c-8d0e-1f2a3b4c5d6e
    def _load_lookback_seconds(self) -> int:
        """
        Read coherence_lookback_seconds from .intent/cim/thresholds.yaml.
        Returns _CFG.lookback_seconds on any load or coercion failure
        so a malformed threshold file does not prevent the cycle from
        running with a sensible default.
        """
        try:
            data = strict_yaml_processor.load_strict(_THRESHOLDS_PATH)
            value = data.get(_LOOKBACK_KEY, _CFG.lookback_seconds)
            return int(value)
        except Exception as exc:
            logger.warning(
                "CoherenceSensorWorker: could not read %s from %s (%s); "
                "using default %ds",
                _LOOKBACK_KEY,
                _THRESHOLDS_PATH,
                exc,
                _CFG.lookback_seconds,
            )
            return _CFG.lookback_seconds
