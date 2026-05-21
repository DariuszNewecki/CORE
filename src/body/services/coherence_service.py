# src/body/services/coherence_service.py

"""
CoherenceService — Body layer service for Constitutional Coherence Checker storage.

Governing ADR: .specs/decisions/ADR-067-constitutional-coherence-checker.md

Constitutional Compliance:
- Body layer service: provides DB access without making decisions.
- No business logic — pure CRUD on core.coherence_runs / core.coherence_candidates.
- Tables created by governor-executed SQL (Section 5); this service does not
  declare ORM models.
- Each mutation method commits, so partial CCC runs are durable across
  long-running LLM-call boundaries.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)

__all__ = ["CoherenceService"]


# ID: be79ccfb-6907-4aa7-abc1-b50af356cf6d
class CoherenceService:
    """
    Body service for Constitutional Coherence Checker storage.

    Stores coherence runs and the candidates they produce, and records triage
    decisions. Triage transitions out of 'unreviewed' decrement the parent
    run's unreviewed counter; when the counter reaches zero the run is closed.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ID: afc36718-af66-4a75-815d-8efafd5ea3fb
    def detach(self) -> None:
        """Release the database session reference."""
        self.session = None

    # ID: 926480f7-0a87-4775-a112-47e716e073af
    async def create_run(self, trigger: str) -> str:
        """
        Insert a new coherence_runs row. Returns the new run_id as a string.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        result = await self.session.execute(
            text(
                "INSERT INTO core.coherence_runs (trigger) "
                "VALUES (:trigger) RETURNING run_id"
            ),
            {"trigger": trigger},
        )
        run_id = str(result.scalar_one())
        await self.session.commit()
        logger.debug("Created coherence run %s (trigger=%s)", run_id, trigger)
        return run_id

    # ID: b34a7fa4-9ea9-4673-b14a-8b728f1df09e
    async def add_candidate(
        self,
        run_id: str,
        relation: str,
        documents: list[str],
        claim: str,
        rationale: str,
    ) -> str:
        """
        Insert one candidate and increment counters on its parent run.
        Returns the new candidate_id as a string.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        insert_result = await self.session.execute(
            text(
                "INSERT INTO core.coherence_candidates "
                "(run_id, relation, documents, claim, rationale) "
                "VALUES (:run_id, :relation, cast(:documents as jsonb), "
                "        :claim, :rationale) "
                "RETURNING candidate_id"
            ),
            {
                "run_id": run_id,
                "relation": relation,
                "documents": json.dumps(documents),
                "claim": claim,
                "rationale": rationale,
            },
        )
        candidate_id = str(insert_result.scalar_one())
        await self.session.execute(
            text(
                "UPDATE core.coherence_runs "
                "SET candidate_count = candidate_count + 1, "
                "    unreviewed_count = unreviewed_count + 1 "
                "WHERE run_id = :run_id"
            ),
            {"run_id": run_id},
        )
        await self.session.commit()
        logger.debug(
            "Added candidate %s (relation=%s) to run %s",
            candidate_id,
            relation,
            run_id,
        )
        return candidate_id

    # ID: b278e656-2ec2-4403-b246-02c9915da37a
    async def triage_candidate(
        self,
        candidate_id: str,
        decision: str,
        note: str | None,
    ) -> dict:
        """
        Record a triage decision on one candidate.

        Transition-aware: the parent run's unreviewed_count is decremented only
        when the candidate moves out of 'unreviewed'. Re-triage of an already-
        triaged candidate updates the decision/note without further counter
        changes. When unreviewed_count reaches zero the run is closed.

        Returns ``{"run_id": str | None, "run_closed": bool}`` so callers can
        report the close-transition. ``run_id`` is None when the candidate
        does not exist; ``run_closed`` is True only when *this* call's
        transition brought unreviewed_count to zero.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")

        lookup = await self.session.execute(
            text(
                "SELECT run_id, triage_decision "
                "FROM core.coherence_candidates WHERE candidate_id = :candidate_id"
            ),
            {"candidate_id": candidate_id},
        )
        row = lookup.fetchone()
        if row is None:
            return {"run_id": None, "run_closed": False}

        run_id = str(row[0])
        was_unreviewed = row[1] == "unreviewed"

        await self.session.execute(
            text(
                "UPDATE core.coherence_candidates "
                "SET triage_decision = :decision, "
                "    triage_note = :note, "
                "    triaged_at = now() "
                "WHERE candidate_id = :candidate_id"
            ),
            {
                "candidate_id": candidate_id,
                "decision": decision,
                "note": note,
            },
        )

        run_closed = False
        if was_unreviewed:
            decrement = await self.session.execute(
                text(
                    "UPDATE core.coherence_runs "
                    "SET unreviewed_count = unreviewed_count - 1 "
                    "WHERE run_id = :run_id "
                    "RETURNING unreviewed_count"
                ),
                {"run_id": run_id},
            )
            new_count = decrement.scalar_one()
            if new_count == 0:
                await self.session.execute(
                    text(
                        "UPDATE core.coherence_runs "
                        "SET run_status = 'closed' "
                        "WHERE run_id = :run_id"
                    ),
                    {"run_id": run_id},
                )
                run_closed = True
                logger.info("Coherence run %s closed (all candidates triaged)", run_id)

        await self.session.commit()
        return {"run_id": run_id, "run_closed": run_closed}

    # ID: 9dbdeb54-1eae-4532-a1a6-d14b23b9b2e0
    async def update_manifest(self, run_id: str, manifest: list[dict]) -> None:
        """
        Replace the input_manifest of a coherence run.

        Called by ``CoherenceChecker.run`` after R1/R2/R3 complete so the
        final coverage manifest (with per-item ``status`` and
        ``skipped_reason``) is persisted in one atomic write.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        await self.session.execute(
            text(
                "UPDATE core.coherence_runs "
                "SET input_manifest = cast(:manifest as jsonb) "
                "WHERE run_id = :run_id"
            ),
            {"run_id": run_id, "manifest": json.dumps(manifest)},
        )
        await self.session.commit()
        logger.debug(
            "Updated input_manifest for coherence run %s (%d entries)",
            run_id,
            len(manifest),
        )

    # ID: af213873-b33c-4847-ad39-4163d5c766d9
    async def get_run(self, run_id: str) -> dict | None:
        """
        Fetch one coherence run by id. Returns None if not found.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        result = await self.session.execute(
            text(
                "SELECT run_id, run_at, trigger, run_status, input_manifest, "
                "       candidate_count, unreviewed_count "
                "FROM core.coherence_runs WHERE run_id = :run_id"
            ),
            {"run_id": run_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return _row_to_run_dict(row)

    # ID: ded2d00c-eed6-4abb-976d-439152b8a9bb
    async def get_latest_run(self) -> dict | None:
        """
        Fetch the most recent coherence run by run_at. Returns None if no runs
        exist.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        result = await self.session.execute(
            text(
                "SELECT run_id, run_at, trigger, run_status, input_manifest, "
                "       candidate_count, unreviewed_count "
                "FROM core.coherence_runs ORDER BY run_at DESC LIMIT 1"
            ),
        )
        row = result.fetchone()
        if row is None:
            return None
        return _row_to_run_dict(row)

    # ID: fc475ed4-c20a-4791-b815-3c9d5338c19a
    async def get_candidates(self, run_id: str) -> list[dict]:
        """
        Fetch all candidates for one run, ordered by created_at.

        Required by `core-admin coherence report` (Section 6) to render the
        candidate list; not in the Section 3 required-methods list but
        unavoidable for the CLI surface. Pure read, no commit.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        result = await self.session.execute(
            text(
                "SELECT candidate_id, run_id, relation, documents, claim, rationale, "
                "       triage_decision, triage_note, created_at, triaged_at "
                "FROM core.coherence_candidates "
                "WHERE run_id = :run_id ORDER BY created_at"
            ),
            {"run_id": run_id},
        )
        return [_row_to_candidate_dict(row) for row in result.fetchall()]

    # ID: 4349ca7b-0046-4ada-a0e9-8ff6f63a64af
    async def get_unreviewed_summary(self) -> dict:
        """
        Return a summary across all open runs:
        ``{"open_runs": int, "unreviewed": int}``.
        """
        if self.session is None:
            raise RuntimeError("CoherenceService error: Session has been detached.")
        result = await self.session.execute(
            text(
                "SELECT COUNT(*) AS open_runs, "
                "       COALESCE(SUM(unreviewed_count), 0) AS unreviewed "
                "FROM core.coherence_runs WHERE run_status = 'open'"
            ),
        )
        row = result.fetchone()
        return {"open_runs": int(row[0]), "unreviewed": int(row[1])}


def _row_to_run_dict(row: Any) -> dict:
    return {
        "run_id": str(row[0]),
        "run_at": row[1],
        "trigger": row[2],
        "run_status": row[3],
        "input_manifest": row[4],
        "candidate_count": row[5],
        "unreviewed_count": row[6],
    }


def _row_to_candidate_dict(row: Any) -> dict:
    return {
        "candidate_id": str(row[0]),
        "run_id": str(row[1]),
        "relation": row[2],
        "documents": row[3],
        "claim": row[4],
        "rationale": row[5],
        "triage_decision": row[6],
        "triage_note": row[7],
        "created_at": row[8],
        "triaged_at": row[9],
    }
