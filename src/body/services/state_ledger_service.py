# src/body/services/state_ledger_service.py
"""
StateLedgerService - Body layer persistence for ADR-169 D1 state observations.

CORE records an observation of its own state at daemon boot and with every
persisted audit run, in core.state_observations: repository HEAD, the
working-tree paths that differ from HEAD, the law of record vs the law
evaluated (ADR-169 D2), and — at boot — the identity of the code loaded.

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
from shared.infrastructure.intent.law_state import (
    LawState,
    law_digest,
    observe_law_state,
)
from shared.logger import getLogger
from shared.workers.blackboard_publisher import _sanitize_payload


logger = getLogger(__name__)

ObservationTrigger = Literal["boot", "audit_run"]


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
    include_code_identity: bool = False,
    audit_run_id: str | None = None,
) -> StateObservation:
    """Observe the repository's state now (read-only).

    ``law_state`` may be passed when the caller already observed the law for
    the audit it is recording, so the ledger row and the verdict describe the
    same observation. ``include_code_identity`` fingerprints ``src/`` as it is
    on disk: at process boot that is the code the process loads.
    """
    law = law_state or observe_law_state(intent_root)
    head_sha: str | None = law.head_sha
    dirty: list[str] = []
    code_identity: str | None = None
    try:
        git = GitService(repo_root)
        head_sha = head_sha or git.get_current_commit()
        dirty = git.changed_paths(".")
        if include_code_identity:
            code_identity = law_digest(git.hash_working_paths("src"))
    except RuntimeError as exc:
        logger.warning("state observation: git failed for %s: %s", repo_root, exc)
    return StateObservation(
        trigger=trigger,
        repo_root=str(repo_root),
        law_state=law,
        head_sha=head_sha,
        dirty_paths=dirty,
        loaded_code_identity=code_identity,
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
