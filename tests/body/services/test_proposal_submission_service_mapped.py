# tests/body/services/test_proposal_submission_service_mapped.py
"""Integration tests: mapped-lane atomic proposal submission (#886, ADR-154
D3b applied to ViolationRemediatorWorker's lane).

Proves the transaction boundary against a real database — not mocks — for
``submit_mapped_proposal``: proposal persistence, ownership-checked finding
deferral, and the caller-supplied safe auto-approval step commit or roll
back together. Mirrors test_proposal_submission_service_ceremony.py's
DB-backed pattern; the approval step under test is the *real*
``ProposalStateManager.approve`` (envelope validation included), passed in
the same closure shape the lane uses.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.proposal_submission_service import (
    MappedSubmissionResult,
    ProposalSubmissionError,
    submit_mapped_proposal,
)
from body.services.service_registry import service_registry
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.session_manager import get_session
from will.autonomy.proposal_state_manager import ProposalStateManager
from will.autonomy.safe_auto_approval_envelope import SafeAutoApprovalDeniedError


pytestmark = [pytest.mark.integration]

_RULE = "workflow.ruff_format_check"


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


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
            "worker_name": f"test_mapped_submission_{str(worker_uuid)[:8]}",
        },
    )
    await session.commit()


async def _seed_claimed_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    *,
    file_path: str,
    status: str = "claimed",
    claimed_by: uuid.UUID | None = None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'audit', :status,
                 :subject, cast(:payload as jsonb), 'reaudit',
                 :claimed_by, now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "status": status,
            "claimed_by": claimed_by or worker_uuid,
            "subject": f"python::{_RULE}::{file_path}",
            "payload": json.dumps({"rule": _RULE, "file_path": file_path}),
        },
    )
    await session.commit()


def _mapped_proposal(
    file_path: str,
    *,
    action_id: str = "fix.format",
    approval_required: bool = False,
    proposal_id: str | None = None,
) -> AutonomousProposal:
    """The persistence-model shape violation_remediator_proposal produces:
    one atomic action targeting *file_path*, scope.files == [file_path]."""
    return AutonomousProposal(
        proposal_id=proposal_id or str(uuid.uuid4()),
        goal="#886 mapped atomic submission test",
        status="pending",
        actions=[
            {
                "action_id": action_id,
                "flow_id": None,
                "parameters": {"write": True, "file_path": file_path},
                "order": 0,
            }
        ],
        scope={"files": [file_path], "modules": [], "symbols": [], "policies": []},
        created_by="violation_remediator_worker",
        approval_required=approval_required,
        constitutional_constraints={"source": "blackboard_findings"},
    )


async def _safe_auto_approve(session: Any, proposal_id: str) -> bool:
    """The lane's approval step: real gate, denial → False, else True."""
    try:
        await ProposalStateManager(session).approve(
            proposal_id,
            approved_by="autonomous_self_promote",
            approval_authority="risk_classification.safe_auto_approval",
        )
    except SafeAutoApprovalDeniedError:
        return False
    return True


async def _proposal_row(session: AsyncSession, proposal_id: str):
    result = await session.execute(
        text(
            "SELECT status, approved_by, approval_authority "
            "FROM core.autonomous_proposals WHERE proposal_id = :pid"
        ),
        {"pid": proposal_id},
    )
    return result.fetchone()


async def _finding_row(session: AsyncSession, finding_id: uuid.UUID):
    result = await session.execute(
        text(
            "SELECT status, payload->>'proposal_id', claimed_by, resolution_mechanism "
            "FROM core.blackboard_entries WHERE id = :id"
        ),
        {"id": finding_id},
    )
    return result.fetchone()


async def _cleanup(
    session: AsyncSession, finding_ids: list[uuid.UUID], proposal_ids: list[str]
) -> None:
    await session.rollback()
    await session.execute(
        text("DELETE FROM core.blackboard_entries WHERE id = ANY(:ids)"),
        {"ids": finding_ids},
    )
    await session.execute(
        delete(AutonomousProposal).where(
            AutonomousProposal.proposal_id.in_(proposal_ids)
        )
    )
    await session.commit()


async def test_safe_submission_commits_proposal_deferral_and_approval_together(
    db_session: AsyncSession,
) -> None:
    """fix.format on src/*.py is inside the safe auto-approval envelope:
    one transaction → APPROVED proposal carrying approval_authority, finding
    deferred_to_proposal linked by id, resolution_mechanism untouched."""
    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    file_path = f"src/t886_{finding_id.hex[:8]}.py"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await _seed_claimed_finding(
        db_session, finding_id, worker_uuid, file_path=file_path
    )
    proposal = _mapped_proposal(file_path)

    try:
        result = await submit_mapped_proposal(
            proposal,
            finding_ids=[str(finding_id)],
            expected_worker_uuid=worker_uuid,
            approval_step=_safe_auto_approve,
        )
        assert result == MappedSubmissionResult(
            proposal_id=proposal.proposal_id, deferred_count=1, auto_approved=True
        )

        async with service_registry.session() as fresh:
            prow = await _proposal_row(fresh, proposal.proposal_id)
            assert prow is not None
            assert prow[0] == "approved"
            assert prow[1] == "autonomous_self_promote"
            assert prow[2] == "risk_classification.safe_auto_approval"
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "deferred_to_proposal"
            assert frow[1] == proposal.proposal_id
            assert frow[3] == "reaudit"
    finally:
        await _cleanup(db_session, [finding_id], [proposal.proposal_id])


async def test_approval_step_failure_rolls_back_proposal_and_deferral(
    db_session: AsyncSession,
) -> None:
    """The #886 auto-approval question, answered by transaction: an approval
    failure after the proposal and deferral would have committed leaves NO
    proposal row and the finding exactly as claimed as before — never a
    committed proposal beside an un-deferred finding, and never a deferred
    finding pointing at a proposal that does not exist."""
    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    file_path = f"src/t886_{finding_id.hex[:8]}.py"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await _seed_claimed_finding(
        db_session, finding_id, worker_uuid, file_path=file_path
    )
    proposal = _mapped_proposal(file_path)

    async def _approval_outage(session: Any, proposal_id: str) -> bool:
        raise RuntimeError("simulated approval-time outage")

    try:
        with pytest.raises(RuntimeError, match="simulated approval-time outage"):
            await submit_mapped_proposal(
                proposal,
                finding_ids=[str(finding_id)],
                expected_worker_uuid=worker_uuid,
                approval_step=_approval_outage,
            )

        async with service_registry.session() as fresh:
            assert await _proposal_row(fresh, proposal.proposal_id) is None
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "claimed"
            assert frow[1] is None
            assert frow[2] == worker_uuid
    finally:
        await _cleanup(db_session, [finding_id], [proposal.proposal_id])


async def test_retry_after_rolled_back_submission_succeeds_cleanly(
    db_session: AsyncSession,
) -> None:
    """Idempotency of the rollback: a rolled-back submission leaves no
    residue, so the same proposal_id + same finding can be resubmitted and
    commit normally on the next attempt."""
    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    file_path = f"src/t886_{finding_id.hex[:8]}.py"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await _seed_claimed_finding(
        db_session, finding_id, worker_uuid, file_path=file_path
    )
    proposal_id = str(uuid.uuid4())

    async def _approval_outage(session: Any, _pid: str) -> bool:
        raise RuntimeError("first attempt fails")

    try:
        with pytest.raises(RuntimeError, match="first attempt fails"):
            await submit_mapped_proposal(
                _mapped_proposal(file_path, proposal_id=proposal_id),
                finding_ids=[str(finding_id)],
                expected_worker_uuid=worker_uuid,
                approval_step=_approval_outage,
            )

        result = await submit_mapped_proposal(
            _mapped_proposal(file_path, proposal_id=proposal_id),
            finding_ids=[str(finding_id)],
            expected_worker_uuid=worker_uuid,
            approval_step=_safe_auto_approve,
        )
        assert result.proposal_id == proposal_id
        assert result.deferred_count == 1
        assert result.auto_approved is True

        async with service_registry.session() as fresh:
            prow = await _proposal_row(fresh, proposal_id)
            assert prow is not None and prow[0] == "approved"
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "deferred_to_proposal"
            assert frow[1] == proposal_id
    finally:
        await _cleanup(db_session, [finding_id], [proposal_id])


async def test_envelope_denial_commits_pending_with_findings_deferred(
    db_session: AsyncSession,
) -> None:
    """#853 governor ruling 6 inside the transaction: check.imports is
    impact_level safe (so the lane attempts auto-approval) but NOT in the
    envelope. Denial is not a failure — the step returns False and the
    proposal commits in PENDING — visible in the approval queue (#885) —
    with its finding deferred and linked."""
    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    file_path = f"src/t886_{finding_id.hex[:8]}.py"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await _seed_claimed_finding(
        db_session, finding_id, worker_uuid, file_path=file_path
    )
    proposal = _mapped_proposal(file_path, action_id="check.imports")

    try:
        result = await submit_mapped_proposal(
            proposal,
            finding_ids=[str(finding_id)],
            expected_worker_uuid=worker_uuid,
            approval_step=_safe_auto_approve,
        )
        assert result.auto_approved is False
        assert result.deferred_count == 1

        async with service_registry.session() as fresh:
            prow = await _proposal_row(fresh, proposal.proposal_id)
            assert prow is not None
            assert prow[0] == "pending"
            assert prow[1] is None
            assert prow[2] is None
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "deferred_to_proposal"
            assert frow[1] == proposal.proposal_id
    finally:
        await _cleanup(db_session, [finding_id], [proposal.proposal_id])


async def test_non_safe_proposal_without_approval_step_stays_pending(
    db_session: AsyncSession,
) -> None:
    """approval_required=True proposals pass no approval step: they commit
    in PENDING with findings deferred and gain no automatic approval path
    (invariant 6). Behaviour unchanged from before #886."""
    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    file_path = f"src/t886_{finding_id.hex[:8]}.py"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await _seed_claimed_finding(
        db_session, finding_id, worker_uuid, file_path=file_path
    )
    proposal = _mapped_proposal(file_path, approval_required=True)

    try:
        result = await submit_mapped_proposal(
            proposal,
            finding_ids=[str(finding_id)],
            expected_worker_uuid=worker_uuid,
            approval_step=None,
        )
        assert result.auto_approved is False

        async with service_registry.session() as fresh:
            prow = await _proposal_row(fresh, proposal.proposal_id)
            assert prow is not None
            assert prow[0] == "pending"
            assert prow[2] is None
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "deferred_to_proposal"
    finally:
        await _cleanup(db_session, [finding_id], [proposal.proposal_id])


async def test_stale_claim_aborts_everything_and_never_runs_approval(
    db_session: AsyncSession,
) -> None:
    """Two findings, one re-claimed by another worker → whole submission
    aborts: no proposal, the still-owned finding untouched, the other
    worker's claim intact, and the approval step never invoked."""
    owned = uuid.uuid4()
    stolen = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    other_worker = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await _ensure_worker_registry_row(db_session, other_worker)
    await _seed_claimed_finding(
        db_session, owned, worker_uuid, file_path=f"src/t886_{owned.hex[:8]}.py"
    )
    await _seed_claimed_finding(
        db_session,
        stolen,
        worker_uuid,
        file_path=f"src/t886_{stolen.hex[:8]}.py",
        claimed_by=other_worker,
    )
    proposal = _mapped_proposal(f"src/t886_{owned.hex[:8]}.py")
    approval_calls: list[str] = []

    async def _counting_step(session: Any, proposal_id: str) -> bool:
        approval_calls.append(proposal_id)
        return True

    try:
        with pytest.raises(ProposalSubmissionError, match="no longer eligible"):
            await submit_mapped_proposal(
                proposal,
                finding_ids=[str(owned), str(stolen)],
                expected_worker_uuid=worker_uuid,
                approval_step=_counting_step,
            )
        assert approval_calls == []

        async with service_registry.session() as fresh:
            assert await _proposal_row(fresh, proposal.proposal_id) is None
            orow = await _finding_row(fresh, owned)
            assert orow is not None and orow[0] == "claimed" and orow[2] == worker_uuid
            srow = await _finding_row(fresh, stolen)
            assert srow is not None and srow[0] == "claimed" and srow[2] == other_worker
    finally:
        await _cleanup(db_session, [owned, stolen], [proposal.proposal_id])


async def test_empty_finding_ids_is_refused() -> None:
    with pytest.raises(ProposalSubmissionError, match="at least one finding_id"):
        await submit_mapped_proposal(
            _mapped_proposal("src/x.py"),
            finding_ids=[],
            expected_worker_uuid=uuid.uuid4(),
        )
