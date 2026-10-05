# src/body/services/state_ledger_service.py
"""
StateLedgerService - Body layer persistence for ADR-169 D1 state observations.

CORE records an observation of its own state at daemon boot, with every
persisted audit run, and — from the StateSensor — on each cycle in which the
state changed (trigger ``cycle``), in core.state_observations: repository
HEAD, the working-tree paths that differ from HEAD, the law of record vs the
law evaluated (ADR-169 D2), and the identity of the code the daemon loaded
(ADR-169 D3, shared.infrastructure.code_identity).

Constitutional standing:
- Layer:  body/services — infrastructure service.
- Append-only: one INSERT per observation; rows are never updated (the table
  refuses UPDATE by trigger).
- git runs through shared GitService (the sole git subprocess sanctuary).
- No LLM calls. No file writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text

from shared.infrastructure.git_service import GitService
from shared.infrastructure.intent.law_state import LawState, observe_law_state
from shared.logger import getLogger
from shared.workers.blackboard_publisher import _sanitize_payload


logger = getLogger(__name__)

ObservationTrigger = Literal["boot", "audit_run", "cycle"]


@dataclass(frozen=True)
# ID: 90099116-815f-4b25-b323-078c570e2d79
class StateObservation:
    """One row of core.state_observations, before it is written."""

    trigger: ObservationTrigger
    repo_root: str
    law_state: LawState
    head_sha: str | None = None
    dirty_paths: list[str] = field(default_factory=list)
    loaded_code_identity: str | None = None
    audit_run_id: str | None = None


# ID: 59be4ae3-e12c-4c25-a96c-3ddce4ab48d5
def observe_state(
    repo_root: Path,
    intent_root: Path,
    trigger: ObservationTrigger,
    *,
    law_state: LawState | None = None,
    loaded_code_identity: str | None = None,
    audit_run_id: str | None = None,
) -> StateObservation:
    """Observe the repository's state now (read-only).

    ``law_state`` may be passed when the caller already observed the law for
    the audit it is recording, so the ledger row and the verdict describe the
    same observation. ``loaded_code_identity`` is the identity the observing
    process captured at boot (shared.infrastructure.code_identity); it is
    recorded as given, never recomputed here — the code on disk now is not
    necessarily the code the process runs.
    """
    law = law_state or observe_law_state(intent_root)
    head_sha: str | None = law.head_sha
    dirty: list[str] = []
    try:
        git = GitService(repo_root)
        head_sha = head_sha or git.get_current_commit()
        dirty = git.changed_paths(".")
    except RuntimeError as exc:
        logger.warning("state observation: git failed for %s: %s", repo_root, exc)
    return StateObservation(
        trigger=trigger,
        repo_root=str(repo_root),
        law_state=law,
        head_sha=head_sha,
        dirty_paths=dirty,
        loaded_code_identity=loaded_code_identity,
        audit_run_id=audit_run_id,
    )


# ID: 726dd090-7aab-4a2d-8d26-adf1a97bd02a
class StateLedgerService:
    """Append-only writer for core.state_observations (ADR-169 D1)."""

    # ID: 3216469e-7943-41a9-a7c2-b9b202e831c6
    async def record(self, session: Any, observation: StateObservation) -> None:
        """INSERT one observation and commit."""
        law = observation.law_state
        await session.execute(
            text(
                """
                INSERT INTO core.state_observations
                    (trigger, repo_root, head_sha, dirty_paths,
                     law_relationship, law_record_digest, law_evaluated_digest,
                     law_drift_paths, loaded_code_identity, audit_run_id)
                VALUES
                    (:trigger, :repo_root, :head_sha, cast(:dirty as jsonb),
                     :relationship, :record_digest, :evaluated_digest,
                     cast(:drift as jsonb), :code_identity,
                     cast(:audit_run_id as uuid))
                """
            ),
            {
                "trigger": observation.trigger,
                "repo_root": observation.repo_root,
                "head_sha": observation.head_sha,
                # The core DB is SQL_ASCII (#359): sanitize path payloads.
                "dirty": json.dumps(_sanitize_payload(observation.dirty_paths)),
                "relationship": law.relationship,
                "record_digest": law.record_digest,
                "evaluated_digest": law.evaluated_digest,
                "drift": json.dumps(_sanitize_payload(law.drift_paths)),
                "code_identity": observation.loaded_code_identity,
                "audit_run_id": observation.audit_run_id,
            },
        )
        await session.commit()
        logger.info(
            "state observation recorded: trigger=%s head=%s law=%s dirty=%d",
            observation.trigger,
            (observation.head_sha or "?")[:12],
            law.relationship,
            len(observation.dirty_paths),
        )

    # ID: d341cb98-c44b-46d3-95cf-d9955e3679ab
    async def latest(self, session: Any, repo_root: str) -> dict[str, Any] | None:
        """The most recent observation for repo_root, or None."""
        result = await session.execute(
            text(
                """
                SELECT head_sha, dirty_paths, law_relationship, law_record_digest,
                       law_evaluated_digest, law_drift_paths, loaded_code_identity
                FROM core.state_observations
                WHERE repo_root = :repo_root
                ORDER BY observed_at DESC
                LIMIT 1
                """
            ),
            {"repo_root": repo_root},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else None

    # ID: 3efda24e-93f1-433e-852e-7e6193c5e8ca
    async def record_if_changed(
        self, observation: StateObservation, session: Any = None
    ) -> bool:
        """Append ``observation`` only when it differs from the latest row.

        Keeps the ledger's history (every change is a row) without one row
        per cycle while nothing changes. Returns True when a row was written.
        Without ``session`` the service opens its own (callers outside Body
        do not hold sessions).
        """
        if session is None:
            from body.services.service_registry import ServiceRegistry

            async with ServiceRegistry.session() as own:
                return await self.record_if_changed(observation, own)
        previous = await self.latest(session, observation.repo_root)
        if previous is not None and observation_key(previous) == observation_key(
            _as_row(observation)
        ):
            return False
        await self.record(session, observation)
        return True


def _as_row(observation: StateObservation) -> dict[str, Any]:
    """The comparable columns of an observation, shaped like a ledger row."""
    law = observation.law_state
    return {
        "head_sha": observation.head_sha,
        "dirty_paths": _sanitize_payload(observation.dirty_paths),
        "law_relationship": law.relationship,
        "law_record_digest": law.record_digest,
        "law_evaluated_digest": law.evaluated_digest,
        "law_drift_paths": _sanitize_payload(law.drift_paths),
        "loaded_code_identity": observation.loaded_code_identity,
    }


# ID: c38b2522-2533-43cb-a268-5299bf306d09
def observation_key(row: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two observations the same state (time and trigger excluded)."""

    def _paths(value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            value = json.loads(value)
        return tuple(sorted(value or []))

    return (
        row.get("head_sha"),
        _paths(row.get("dirty_paths")),
        row.get("law_relationship"),
        row.get("law_record_digest"),
        row.get("law_evaluated_digest"),
        _paths(row.get("law_drift_paths")),
        row.get("loaded_code_identity"),
    )
