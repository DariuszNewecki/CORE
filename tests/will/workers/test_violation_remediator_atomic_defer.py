"""Regression tests for #886 — ViolationRemediatorWorker's create-then-defer
race must not be able to leave a durable Proposal whose source finding is
still ``claimed`` (ADR-154 D3b applied to the mapped lane).

Written against the *invariant*, not against either implementation, so the
same file runs at the pre-fix and post-fix SHAs:

    A Proposal row that cites a finding in ``constitutional_constraints
    .finding_ids`` MUST NOT be durable while that finding is still
    ``claimed`` — either both ledgers link (finding ``deferred_to_proposal``
    with the proposal_id on its payload) or neither side exists.

Pre-fix, ``create_proposal`` commits in its own transaction and the later
fail-soft ``defer_to_proposal`` call is a separate transaction, so a defer
failure leaves exactly the forbidden state. Post-fix, creation + deferral
(+ safe auto-approval) are one Body-owned transaction
(``submit_mapped_proposal``) and a deferral failure rolls the proposal back.

Real ``core_test`` persistence, real ``create_proposal``/submission/state
manager; only the worker's *loaders* (finding claim, remediation map, active-
proposal index, circuit breaker, committed-file gate) and its report sink
are stubbed — those are inputs to the transaction under test, not part of it.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session
from will.workers.violation_remediator import ViolationRemediatorWorker


pytestmark = [pytest.mark.integration]

_RULE = "workflow.ruff_format_check"
_REF_ID = "fix.format"  # in the #853 safe_auto_approval_envelope → auto-approves


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


@pytest.fixture
def worker() -> ViolationRemediatorWorker:
    core_context = MagicMock()
    core_context.git_service.repo_path = "/fake/repo"
    return ViolationRemediatorWorker(
        core_context=core_context, declaration_name="violation_remediator"
    )


async def _ensure_worker_registry_row(
    session: AsyncSession, worker_uuid: uuid.UUID
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO core.worker_registry
                (worker_uuid, worker_name, worker_class, phase)
            VALUES (:worker_uuid, :worker_name, 'acting', 'remediation')
            ON CONFLICT (worker_uuid) DO NOTHING
            """
        ),
        {
            "worker_uuid": worker_uuid,
            "worker_name": f"test_886_{str(worker_uuid)[:8]}",
        },
    )
    await session.commit()


async def _seed_claimed_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
    *,
    posted_by: uuid.UUID,
    claimed_by: uuid.UUID,
    file_path: str,
) -> dict[str, Any]:
    """Seed one canonical mapped-lane finding already at ``claimed`` (the
    state ``claim_findings_by_patterns`` leaves it in) and return the dict
    shape ``load_open_findings`` hands the worker."""
    payload = {"rule": _RULE, "check_id": _RULE, "file_path": file_path}
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'audit', 'claimed',
                 :subject, cast(:payload as jsonb), 'reaudit',
                 :claimed_by, now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": posted_by,
            "claimed_by": claimed_by,
            "subject": f"python::{_RULE}::{file_path}",
            "payload": json.dumps(payload),
        },
    )
    await session.commit()
    return {
        "id": str(finding_id),
        "subject": f"python::{_RULE}::{file_path}",
        "payload": payload,
    }


async def _proposals_citing(session: AsyncSession, finding_id: uuid.UUID) -> list:
    result = await session.execute(
        text(
            """
            SELECT proposal_id, status
            FROM core.autonomous_proposals
            WHERE constitutional_constraints->'finding_ids' ? :fid
            """
        ),
        {"fid": str(finding_id)},
    )
    return result.fetchall()


async def _finding_row(session: AsyncSession, finding_id: uuid.UUID):
    result = await session.execute(
        text(
            "SELECT status, payload->>'proposal_id', claimed_by "
            "FROM core.blackboard_entries WHERE id = :id"
        ),
        {"id": finding_id},
    )
    return result.fetchone()


async def _cleanup(session: AsyncSession, finding_id: uuid.UUID) -> None:
    await session.rollback()
    await session.execute(
        text(
            "DELETE FROM core.autonomous_proposals "
            "WHERE constitutional_constraints->'finding_ids' ? :fid"
        ),
        {"fid": str(finding_id)},
    )
    await session.execute(
        text("DELETE FROM core.blackboard_entries WHERE id = :id"),
        {"id": finding_id},
    )
    await session.commit()


class _DeferOutageService:
    """The real BlackboardService with the two-step lane's deferral call
    replaced by an outage. Pre-fix this is the exact #886 trigger; post-fix
    the deferral no longer goes through this method at all."""

    def __init__(self, real: Any) -> None:
        self._real = real

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    async def defer_entries_to_proposal(self, entry_ids: list[str], proposal_id: str):
        raise RuntimeError("simulated deferral outage after proposal commit")


async def _run_lane(
    worker: ViolationRemediatorWorker,
    findings: list[dict[str, Any]],
    *,
    blackboard_service: Any,
) -> dict[str, Any]:
    """Drive run() through the real create path with loaders stubbed."""
    worker._load_open_findings = AsyncMock(return_value=findings)
    worker._get_remediation_map = MagicMock(
        return_value={
            _RULE: {"ref_id": _REF_ID, "ref_kind": "action", "status": "ACTIVE"}
        }
    )
    worker._get_active_proposal_id_by_action_file = AsyncMock(return_value={})
    worker._check_circuit_breaker = AsyncMock(return_value=(0, None, None, None))
    worker._is_file_committed = MagicMock(return_value=True)
    worker._blackboard_service = AsyncMock(return_value=blackboard_service)
    worker.post_report = AsyncMock()
    worker.post_heartbeat = AsyncMock()

    with (
        patch("will.workers.violation_remediator.load_vocabulary_projection") as vp,
        patch("will.workers.violation_remediator.load_circuit_breaker_config") as cb,
    ):
        vp.return_value = MagicMock()
        cb.return_value = MagicMock(threshold_n=5)
        await worker.run()

    return worker.post_report.call_args[1]["payload"]


async def test_deferral_outage_cannot_leave_durable_proposal_with_claimed_finding(
    db_session: AsyncSession, worker: ViolationRemediatorWorker
) -> None:
    """#886 core case. The deferral step fails after the proposal would have
    committed. The forbidden durable state is: a Proposal citing the finding
    exists AND the finding is still ``claimed``."""
    finding_id = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker._worker_uuid)
    finding = await _seed_claimed_finding(
        db_session,
        finding_id,
        posted_by=worker._worker_uuid,
        claimed_by=worker._worker_uuid,
        file_path=f"src/t886_{finding_id.hex[:8]}.py",
    )
    real_service = await service_registry.get_blackboard_service()

    try:
        await _run_lane(
            worker, [finding], blackboard_service=_DeferOutageService(real_service)
        )

        async with service_registry.session() as fresh:
            proposals = await _proposals_citing(fresh, finding_id)
            row = await _finding_row(fresh, finding_id)
            assert row is not None
            status, linked_proposal_id, _claimed_by = row

            if proposals:
                # A durable proposal exists → the finding MUST be linked to it.
                assert status == "deferred_to_proposal", (
                    f"#886: proposal {proposals[0][0]} is durable but its source "
                    f"finding is still {status!r} — the two ledgers disagree"
                )
                assert linked_proposal_id == proposals[0][0]
            else:
                # No durable proposal → the finding must not claim to be deferred.
                assert status != "deferred_to_proposal"
    finally:
        await _cleanup(db_session, finding_id)


async def test_finding_reclaimed_by_another_worker_creates_no_proposal(
    db_session: AsyncSession, worker: ViolationRemediatorWorker
) -> None:
    """ADR-154 D5 eligibility guard, mapped lane: a finding no longer claimed
    by THIS worker is not this submission's to defer. Nothing may persist.
    Pre-fix the unguarded ``status IN ('open','claimed')`` deferral silently
    steals the other worker's claim and the proposal commits."""
    finding_id = uuid.uuid4()
    other_worker = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker._worker_uuid)
    await _ensure_worker_registry_row(db_session, other_worker)
    finding = await _seed_claimed_finding(
        db_session,
        finding_id,
        posted_by=worker._worker_uuid,
        claimed_by=other_worker,
        file_path=f"src/t886_{finding_id.hex[:8]}.py",
    )
    real_service = await service_registry.get_blackboard_service()

    try:
        payload = await _run_lane(worker, [finding], blackboard_service=real_service)

        async with service_registry.session() as fresh:
            proposals = await _proposals_citing(fresh, finding_id)
            assert proposals == [], (
                "a proposal was persisted for a finding this worker no longer "
                f"holds the claim on: {proposals}"
            )
            row = await _finding_row(fresh, finding_id)
            assert row is not None
            assert row[0] != "deferred_to_proposal"
            assert row[1] is None, "finding must not carry a proposal_id link"
        assert payload["proposals_created"] == 0
        assert payload["entries_deferred"] == 0
    finally:
        await _cleanup(db_session, finding_id)


async def test_successful_create_links_both_ledgers_and_auto_approves(
    db_session: AsyncSession, worker: ViolationRemediatorWorker
) -> None:
    """Happy path: one transaction leaves proposal APPROVED (fix.format on a
    src/*.py target is inside the safe auto-approval envelope), finding
    ``deferred_to_proposal`` carrying that proposal_id, and the run report
    counting the deferral."""
    finding_id = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker._worker_uuid)
    finding = await _seed_claimed_finding(
        db_session,
        finding_id,
        posted_by=worker._worker_uuid,
        claimed_by=worker._worker_uuid,
        file_path=f"src/t886_{finding_id.hex[:8]}.py",
    )
    real_service = await service_registry.get_blackboard_service()

    try:
        payload = await _run_lane(worker, [finding], blackboard_service=real_service)

        async with service_registry.session() as fresh:
            proposals = await _proposals_citing(fresh, finding_id)
            assert len(proposals) == 1, proposals
            proposal_id, proposal_status = proposals[0]
            assert proposal_status == "approved"
            row = await _finding_row(fresh, finding_id)
            assert row is not None
            assert row[0] == "deferred_to_proposal"
            assert row[1] == proposal_id
        assert payload["proposals_created"] == 1
        assert payload["entries_deferred"] == 1
    finally:
        await _cleanup(db_session, finding_id)
