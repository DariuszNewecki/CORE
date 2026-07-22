# src/shared/workers/blackboard_publisher.py

"""BlackboardPublisher — extracted blackboard write surface for Worker.

Holds the six public methods (post_finding, post_artifact_finding,
post_report, post_heartbeat, post_observation, _post_entry) and their
supporting helpers that were previously inlined on Worker.  Worker
constructs one at __init__ time and thin-wraps all six methods so the
subclass API is unchanged.

Testing benefit: workers can be tested by injecting a FakePublisher
(or unittest.mock.AsyncMock) instead of requiring a live DB session.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)

# Non-terminal finding statuses — the scope of the active-finding dedup
# invariant (the partial unique index uq_active_finding_identity). A finding in
# any of these states is "live" and must be unique per (subject,
# resolution_mechanism); terminal statuses may coexist as history.
_NON_TERMINAL_FINDING_STATUSES = frozenset({"open", "claimed", "awaiting_reaudit"})

# PostgreSQL DB is SQL_ASCII encoded — non-ASCII characters cause
# UntranslatableCharacterError on insert. Sanitize all payload strings.
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")

# Terminal statuses per .intent/META/enums.json (blackboard_entry_status).
_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        "resolved",
        "abandoned",
        "suppressed",
        "dry_run_complete",
        "indeterminate",
        "deferred_to_proposal",
    }
)


def _sanitize_str(value: str) -> str:
    return _NON_ASCII_RE.sub("?", value)


def _sanitize_payload(obj: Any) -> Any:
    """Recursively sanitize all strings in a payload to printable ASCII.

    Dict keys are sanitized in addition to values — JSONB write paths
    under SQL_ASCII reject non-ASCII in keys just as they do in values.
    """
    if isinstance(obj, str):
        return _sanitize_str(obj)
    if isinstance(obj, dict):
        return {_sanitize_payload(k): _sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(i) for i in obj]
    return obj


# ID: a3b7c9d1-e5f2-4a8b-9c0d-1e3f5a7b9c2d
class BlackboardPublisher:
    """Blackboard write surface for a single Worker identity.

    Constructed by Worker.__init__ after the declaration is loaded.
    Holds no state beyond the four identity fields needed to write
    constitutionally-attributed blackboard entries.
    """

    def __init__(
        self,
        *,
        worker_uuid: uuid.UUID,
        worker_name: str,
        phase: str,
        declaration: dict[str, Any],
    ) -> None:
        self._worker_uuid = worker_uuid
        self._worker_name = worker_name
        self._phase = phase
        self._declaration = declaration

    # ID: f1e2d3c4-b5a6-4789-8a9b-0c1d2e3f4a5b
    async def post_finding(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        resolution_mechanism: str,
    ) -> uuid.UUID:
        """Post a new finding to the blackboard. Returns the entry ID.

        See Worker.post_finding for the full contract description.
        """
        return await self._post_entry(
            entry_type="finding",
            subject=subject,
            payload=payload,
            status="open",
            resolution_mechanism=resolution_mechanism,
        )

    # ID: 27e3b26f-4a87-441b-9f66-d020f5089751
    async def post_artifact_finding(
        self,
        artifact_type: str,
        sub_namespace: str,
        identity_key_value: str,
        payload: dict[str, Any],
    ) -> uuid.UUID:
        """Post a finding under the ADR-091 D2 canonical subject format.

        See Worker.post_artifact_finding for the full contract description.
        """
        scope = self._declaration["mandate"].get("scope") or {}
        declared_types = scope.get("artifact_type") or []
        declared_namespace = scope.get("rule_namespace")

        if declared_types and artifact_type not in declared_types:
            raise ValueError(
                f"post_artifact_finding: artifact_type {artifact_type!r} not in "
                f"declared mandate.scope.artifact_type {declared_types!r}. "
                f"Per ADR-091 D2, sensors may only emit findings under "
                f"artifact types they have declared they observe."
            )
        if not declared_types:
            logger.debug(
                "post_artifact_finding called by %s with no declared "
                "artifact_type; ADR-091 Phase 1 transition allowance applies",
                self._worker_name,
            )

        if declared_namespace:
            if sub_namespace != declared_namespace and not sub_namespace.startswith(
                f"{declared_namespace}."
            ):
                raise ValueError(
                    f"post_artifact_finding: sub_namespace {sub_namespace!r} "
                    f"must equal declared rule_namespace {declared_namespace!r} "
                    f"or extend it via dotted suffix. Per ADR-091 D2 the "
                    f"sub-namespace must equal or extend the sensor's declared "
                    f"rule_namespace."
                )
        else:
            logger.debug(
                "post_artifact_finding called by %s with no declared "
                "rule_namespace; ADR-091 Phase 1 transition allowance applies",
                self._worker_name,
            )

        subject = f"{artifact_type}::{sub_namespace}::{identity_key_value}"
        return await self.post_finding(
            subject=subject,
            payload=payload,
            resolution_mechanism="reaudit",
        )

    # ID: 9ca752ac-d9df-47b0-9314-0925f6963b00
    async def post_report(self, subject: str, payload: dict[str, Any]) -> uuid.UUID:
        """Post a completion report to the blackboard."""
        return await self._post_entry(
            entry_type="report",
            subject=subject,
            payload=payload,
            status="resolved",
        )

    # ID: 4d5e6f7a-8b9c-4d0e-1f2a-3b4c5d6e7f8a
    async def post_heartbeat(self) -> uuid.UUID:
        """Post a heartbeat — proves worker is alive and constitutionally compliant."""
        return await self._post_entry(
            entry_type="heartbeat",
            subject="worker.heartbeat",
            payload={"worker": self._worker_name, "ts": datetime.now(UTC).isoformat()},
            status="resolved",
        )

    # ID: 5e6f7a8b-9c0d-4e1f-2a3b-4c5d6e7f8a9b
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> uuid.UUID:
        """Post an observability finding that is terminal at creation.

        See Worker.post_observation for the full contract description.
        """
        if status not in _TERMINAL_STATUSES:
            raise ValueError(
                f"post_observation requires a terminal status (got '{status}'). "
                f"Permitted: {sorted(_TERMINAL_STATUSES)}. "
                f"Use post_finding for status='open' (actionable findings) "
                f"or post_report for status='resolved' completion records."
            )
        if status == "indeterminate":
            from sqlalchemy import text

            async with get_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT 1 FROM core.blackboard_entries
                        WHERE subject = :subject
                          AND status = 'indeterminate'
                          AND entry_type = 'finding'
                        LIMIT 1
                        """
                    ),
                    {"subject": subject},
                )
                if result.first() is not None:
                    raise ValueError(
                        f"post_observation refuses duplicate indeterminate "
                        f"post for subject={subject!r}. Indeterminate "
                        f"findings are permanent until explicit governor "
                        f"revival; re-emission is a contract violation. "
                        f"Use BlackboardService."
                        f"fetch_active_finding_subjects_by_prefix to dedup "
                        f"before posting."
                    )
        return await self._post_entry(
            entry_type="finding",
            subject=subject,
            payload=payload,
            status=status,
            resolution_mechanism="human",
        )

    async def _post_entry(
        self,
        *,
        entry_type: str,
        subject: str,
        payload: dict[str, Any],
        status: str,
        resolution_mechanism: str | None = None,
    ) -> uuid.UUID:
        """Write a constitutional record to the blackboard.

        A non-terminal FINDING is written as an atomic dedup upsert keyed on the
        canonical active-finding identity (subject, resolution_mechanism): a
        second poster of the same standing finding collapses into the existing
        row (occurrence_count += 1, payload = latest evidence, updated_at bumped)
        instead of manufacturing a duplicate open row. DB-enforced by the partial
        unique index uq_active_finding_identity — race-proof, not a
        SELECT-then-INSERT guard, and covering every non-terminal state. The
        original evidence is retained in first_payload. All other writes
        (non-findings, terminal-status findings) remain plain inserts.
        """
        from sqlalchemy import text

        entry_id = uuid.uuid4()
        payload_json = json.dumps(_sanitize_payload(payload))
        dedup_finding = (
            entry_type == "finding" and status in _NON_TERMINAL_FINDING_STATUSES
        )

        async with get_session() as session:
            async with session.begin():
                if dedup_finding:
                    result = await session.execute(
                        text(
                            """
                            insert into core.blackboard_entries
                                (id, worker_uuid, entry_type, phase, status, subject,
                                 payload, first_payload, resolution_mechanism, resolved_at,
                                 last_seen_at)
                            values
                                (:id, :worker_uuid, 'finding', :phase, :status, :subject,
                                 cast(:payload as jsonb), cast(:payload as jsonb),
                                 :resolution_mechanism, null, now())
                            on conflict (subject, resolution_mechanism)
                                where entry_type = 'finding'
                                  and status in ('open', 'claimed', 'awaiting_reaudit')
                            do update set
                                occurrence_count = core.blackboard_entries.occurrence_count + 1,
                                payload = excluded.payload,
                                last_seen_at = now(),
                                updated_at = now()
                            returning id
                            """
                        ),
                        {
                            "id": entry_id,
                            "worker_uuid": self._worker_uuid,
                            "phase": self._phase,
                            "status": status,
                            "subject": subject,
                            "payload": payload_json,
                            "resolution_mechanism": resolution_mechanism,
                        },
                    )
                    row = result.first()
                    if row is not None:
                        entry_id = row[0]
                else:
                    await session.execute(
                        text(
                            """
                            insert into core.blackboard_entries
                                (id, worker_uuid, entry_type, phase, status, subject, payload, resolution_mechanism, resolved_at)
                            values
                                (:id, :worker_uuid, :entry_type, :phase, :status, :subject, cast(:payload as jsonb),
                                 :resolution_mechanism,
                                 case when :status in ('resolved', 'abandoned', 'indeterminate') then now() else null end)
                        """
                        ),
                        {
                            "id": entry_id,
                            "worker_uuid": self._worker_uuid,
                            "entry_type": entry_type,
                            "phase": self._phase,
                            "status": status,
                            "subject": subject,
                            "payload": payload_json,
                            "resolution_mechanism": resolution_mechanism,
                        },
                    )

                if entry_type == "heartbeat":
                    await session.execute(
                        text(
                            """
                            update core.worker_registry
                            set last_heartbeat = now()
                            where worker_uuid = :worker_uuid
                        """
                        ),
                        {"worker_uuid": self._worker_uuid},
                    )

        logger.debug(
            "Blackboard entry posted: type=%s subject=%s id=%s",
            entry_type,
            subject,
            entry_id,
        )
        return entry_id
