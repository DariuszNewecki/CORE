# src/body/services/representation_coherence_service.py

"""
RepresentationCoherenceService — Body layer service for ADR-070 D6 verdict line.

Governing ADR: .specs/decisions/ADR-070-source-projection-coherence.md

Constitutional Compliance:
- Body layer service: provides DB access without making decisions.
- Reads .intent/governance/projections.yaml (inventory) and derives per-pair
  state from existing observable signals (blackboard reports, worker_registry
  heartbeats, open findings under each pair's rule_id).
- No business logic about remediation — the service reports, it does not
  prescribe. Drift is named through the existing finding lifecycle; this
  service only summarizes.

Used by: src/cli/resources/code/audit.py (D6 composite verdict line)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text

from body.services.session_attached_service import SessionAttachedService
from shared.logger import getLogger


logger = getLogger(__name__)

__all__ = ["RepresentationCoherenceService"]


_INVENTORY_PATH = Path(".intent/governance/projections.yaml")

# How long a writer-as-sensor pair's signal stays "fresh" before being
# considered sensor-stale. Conservative default — 2x the longest declared
# crawler interval (600s in repo_crawler.yaml) gives 1200s. Per-pair
# overrides via inventory entry's `freshness_seconds` field when present.
_DEFAULT_FRESHNESS_SECONDS = 1200


# ID: 6a8d9c1e-2b4f-4d3a-9c7e-5f8b1a3d6c9e
class RepresentationCoherenceService(SessionAttachedService):
    """
    Reads the projection inventory and derives per-pair coherence state.

    Returns aggregated state for the audit advisory line (ADR-070 D6).
    Per-pair details surface through findings under each pair's rule_id;
    this service produces the summary roll-up only.
    """

    # ID: a3f5d7c9-1e2b-4a6d-8c9f-3e5d7b9c1a4e
    async def get_summary(self) -> dict[str, Any]:
        """
        Return a roll-up of inventory state for the audit advisory line.

        Returns:
            {
                "inventory_loaded": bool,
                "pairs_declared": int,
                "in_lease": int,
                "drifted": int,
                "sensor_stale": int,
                "last_check_at": datetime | None,
            }

        `inventory_loaded=False` indicates the inventory file is absent or
        unreadable. `pairs_declared=0` with loaded=True indicates the
        inventory exists but declares no pairs (pre-first-pair state).
        """
        inventory = _load_inventory()
        if inventory is None:
            return {
                "inventory_loaded": False,
                "pairs_declared": 0,
                "in_lease": 0,
                "drifted": 0,
                "sensor_stale": 0,
                "last_check_at": None,
            }

        pairs = inventory.get("projections", []) or []
        if not pairs:
            return {
                "inventory_loaded": True,
                "pairs_declared": 0,
                "in_lease": 0,
                "drifted": 0,
                "sensor_stale": 0,
                "last_check_at": None,
            }

        in_lease = 0
        drifted = 0
        sensor_stale = 0
        latest_check: datetime | None = None

        for pair in pairs:
            state = await self._get_pair_state(pair)
            if state["status"] == "in_lease":
                in_lease += 1
            elif state["status"] == "drifted":
                drifted += 1
            elif state["status"] == "sensor_stale":
                sensor_stale += 1

            if state["last_check_at"] is not None:
                if latest_check is None or state["last_check_at"] > latest_check:
                    latest_check = state["last_check_at"]

        return {
            "inventory_loaded": True,
            "pairs_declared": len(pairs),
            "in_lease": in_lease,
            "drifted": drifted,
            "sensor_stale": sensor_stale,
            "last_check_at": latest_check,
        }

    async def _get_pair_state(self, pair: dict[str, Any]) -> dict[str, Any]:
        """
        Derive the current state of one projection pair.

        States:
          - in_lease:     sensor recently heartbeated; no open drift findings
          - drifted:      one or more open findings under the pair's rule_id
          - sensor_stale: sensor has not heartbeated within the freshness window
        """
        session = self._require_session()
        sensor_worker_name = pair.get("sensor_worker", "")
        rule_id = pair.get("rule_id", "")
        freshness_seconds = pair.get("freshness_seconds", _DEFAULT_FRESHNESS_SECONDS)

        # Most recent heartbeat for the declared sensor worker.
        heartbeat_result = await session.execute(
            text(
                """
                SELECT last_heartbeat
                FROM core.worker_registry
                WHERE declaration_name = :name
                ORDER BY last_heartbeat DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"name": sensor_worker_name},
        )
        heartbeat_row = heartbeat_result.fetchone()
        last_heartbeat: datetime | None = heartbeat_row[0] if heartbeat_row else None

        # Sensor-stale check: if no heartbeat at all, OR last heartbeat older
        # than the freshness window, the sensor is not observable.
        if last_heartbeat is None:
            return {"status": "sensor_stale", "last_check_at": None}
        now = datetime.now(UTC)
        # Heartbeats persist as TIMESTAMPTZ but may be returned naive on some
        # drivers; coerce defensively.
        if last_heartbeat.tzinfo is None:
            last_heartbeat = last_heartbeat.replace(tzinfo=UTC)
        if now - last_heartbeat > timedelta(seconds=freshness_seconds):
            return {"status": "sensor_stale", "last_check_at": last_heartbeat}

        # Drift check: any open findings under this pair's rule_id.
        # Writer-as-sensor pairs (remediation.mode: inline) post findings
        # with status='resolved' directly, so they never count as drifted
        # here even when a reap happened — which is the correct semantic
        # per ADR-070 D4 (drift was detected and immediately remediated).
        if rule_id:
            drift_result = await session.execute(
                text(
                    """
                    SELECT count(*) FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject = :rule_id
                      AND status = 'open'
                    """
                ),
                {"rule_id": rule_id},
            )
            open_count = int(drift_result.scalar_one() or 0)
            if open_count > 0:
                return {"status": "drifted", "last_check_at": last_heartbeat}

        return {"status": "in_lease", "last_check_at": last_heartbeat}


def _load_inventory() -> dict[str, Any] | None:
    """
    Load the projection inventory from .intent/governance/projections.yaml.

    Returns None if the file is absent or unparseable — the audit advisory
    line treats this as "no pairs declared." A failure to load is not
    raised because the advisory line must not block audit completion.
    """
    if not _INVENTORY_PATH.exists():
        return None
    try:
        return yaml.safe_load(_INVENTORY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(
            "RepresentationCoherenceService: failed to load %s: %s",
            _INVENTORY_PATH,
            exc,
        )
        return None
