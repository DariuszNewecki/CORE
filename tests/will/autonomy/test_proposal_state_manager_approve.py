"""Tests for ProposalStateManager.approve() — URS NFR.5 enforcement.

Cases A/B/C of the Band B test surface for issue #146 + #165.
ALLOWED_APPROVAL_AUTHORITIES is the closed set written to the proposal row;
the CHECK constraint validating that set is exercised separately in
tests/infra/test_approval_authority_constraint.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from will.autonomy.proposal_state_manager import (
    ProposalNotFoundError,
    ProposalStateManager,
    SafeAutoApprovalDeniedError,
)


pytestmark = [pytest.mark.integration]

_ENVELOPE_FILE_PATH = "src/approve_test_fixture.py"


def _draft_row(
    proposal_id: str,
    *,
    validation_checks: list[str] | None = None,
    validation_results: dict[str, bool] | None = None,
    actions: list[dict] | None = None,
    scope: dict | None = None,
) -> AutonomousProposal:
    """Construct a minimal valid AutonomousProposal in DRAFT for tests.

    Defaults to a safe-auto-approval-envelope-compliant shape (#853):
    fix.format targeting a single src/ Python file, declared consistently
    in scope.files — so tests that don't care about the envelope (falsy/
    unknown authority, the governor-lane validation gate) keep working
    unchanged, and only tests that explicitly want an out-of-envelope
    shape need to override actions/scope.
    """
    return AutonomousProposal(
        proposal_id=proposal_id,
        goal="approve() unit test",
        status="draft",
        actions=actions
        if actions is not None
        else [
            {
                "action_id": "fix.format",
                "parameters": {"file_path": _ENVELOPE_FILE_PATH},
                "order": 0,
            }
        ],
        scope=scope
        if scope is not None
        else {
            "files": [_ENVELOPE_FILE_PATH],
            "modules": [],
            "symbols": [],
            "policies": [],
        },
        constitutional_constraints={},
        approval_required=False,
        created_at=datetime.now(UTC),
        validation_checks=validation_checks or [],
        validation_results=validation_results or {},
    )


async def _delete(db_session: AsyncSession, proposal_id: str) -> None:
    await db_session.rollback()
    await db_session.execute(
        delete(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    await db_session.commit()


async def _fetch(
    db_session: AsyncSession, proposal_id: str
) -> AutonomousProposal | None:
    result = await db_session.execute(
        select(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    return result.scalar_one_or_none()


async def test_approve_happy_path(db_session: AsyncSession) -> None:
    """Case A: approve() writes status, approved_by, approved_at, approval_authority."""
    proposal_id = f"test-approve-A-{uuid.uuid4().hex[:8]}"
    db_session.add(_draft_row(proposal_id))
    await db_session.commit()

    try:
        await ProposalStateManager(db_session).approve(
            proposal_id,
            approved_by="autonomous_self_promote",
            approval_authority="risk_classification.safe_auto_approval",
        )
        await db_session.commit()

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "approved"
        assert row.approved_by == "autonomous_self_promote"
        assert row.approved_at is not None
        assert row.approval_authority == "risk_classification.safe_auto_approval"
    finally:
        await _delete(db_session, proposal_id)


@pytest.mark.parametrize("falsy", [None, ""])
async def test_approve_rejects_falsy_authority(
    db_session: AsyncSession, falsy: str | None
) -> None:
    """Case B: approve() raises ValueError on falsy authority and issues no UPDATE."""
    proposal_id = f"test-approve-B-{uuid.uuid4().hex[:8]}"
    db_session.add(_draft_row(proposal_id))
    await db_session.commit()

    try:
        with pytest.raises(ValueError, match=r"NFR\.5"):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="autonomous_self_promote",
                approval_authority=falsy,
            )

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "draft"
        assert row.approval_authority is None
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_rejects_unknown_authority(db_session: AsyncSession) -> None:
    """Case C: approve() raises ValueError on unknown authority; lists allowed set."""
    proposal_id = f"test-approve-C-{uuid.uuid4().hex[:8]}"
    db_session.add(_draft_row(proposal_id))
    await db_session.commit()

    try:
        with pytest.raises(ValueError) as excinfo:
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="autonomous_self_promote",
                approval_authority="made_up.value",
            )
        msg = str(excinfo.value)
        assert "risk_classification.safe_auto_approval" in msg
        assert "principal.governor" in msg

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "draft"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_unknown_uuid_raises_not_found(
    db_session: AsyncSession,
) -> None:
    """approve() raises ProposalNotFoundError when UPDATE matches 0 rows (#273)."""
    bogus_id = f"does-not-exist-{uuid.uuid4().hex}"

    with pytest.raises(ProposalNotFoundError) as excinfo:
        await ProposalStateManager(db_session).approve(
            bogus_id,
            approved_by="cli_admin",
            approval_authority="principal.governor",
        )
    assert bogus_id in str(excinfo.value)


async def test_reject_unknown_uuid_raises_not_found(
    db_session: AsyncSession,
) -> None:
    """reject() raises ProposalNotFoundError when UPDATE matches 0 rows (#273)."""
    bogus_id = f"does-not-exist-{uuid.uuid4().hex}"

    with pytest.raises(ProposalNotFoundError) as excinfo:
        await ProposalStateManager(db_session).reject(bogus_id, reason="test rejection")
    assert bogus_id in str(excinfo.value)


async def test_approve_blocks_on_unmet_validation_gate(
    db_session: AsyncSession,
) -> None:
    """ADR-109 #654: a proposal declaring validation_checks cannot be approved
    while a declared check is not recorded passing; the gate raises and leaves
    the proposal in draft."""
    proposal_id = f"test-gate-block-{uuid.uuid4().hex[:8]}"
    db_session.add(
        _draft_row(
            proposal_id,
            validation_checks=["assisted.validate_diff"],
            validation_results={"assisted.validate_diff": False},
        )
    )
    await db_session.commit()

    try:
        with pytest.raises(ValueError, match="validation"):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="cli_admin",
                approval_authority="principal.governor",
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "draft"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_passes_when_validation_gate_met(
    db_session: AsyncSession,
) -> None:
    """ADR-109 #654: once every declared check is recorded passing, approve()
    proceeds to status='approved' normally."""
    proposal_id = f"test-gate-pass-{uuid.uuid4().hex[:8]}"
    db_session.add(
        _draft_row(
            proposal_id,
            validation_checks=["assisted.validate_diff"],
            validation_results={"assisted.validate_diff": True},
        )
    )
    await db_session.commit()

    try:
        await ProposalStateManager(db_session).approve(
            proposal_id,
            approved_by="cli_admin",
            approval_authority="principal.governor",
        )
        await db_session.commit()

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "approved"
    finally:
        await _delete(db_session, proposal_id)


# --- #853: the safe auto-approval envelope, enforced centrally in approve() -


async def test_approve_denies_safe_auto_approval_outside_envelope(
    db_session: AsyncSession,
) -> None:
    """Governor rulings 1/5: an action not in the envelope raises
    SafeAutoApprovalDeniedError and the row is left completely untouched
    (still draft, no approval fields set) — the UPDATE never runs."""
    proposal_id = f"test-envelope-deny-{uuid.uuid4().hex[:8]}"
    db_session.add(
        _draft_row(
            proposal_id,
            actions=[
                {
                    "action_id": "check.imports",
                    "parameters": {"file_path": _ENVELOPE_FILE_PATH},
                    "order": 0,
                }
            ],
            scope={
                "files": [_ENVELOPE_FILE_PATH],
                "modules": [],
                "symbols": [],
                "policies": [],
            },
        )
    )
    await db_session.commit()

    try:
        with pytest.raises(SafeAutoApprovalDeniedError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="autonomous_self_promote",
                approval_authority="risk_classification.safe_auto_approval",
            )

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "draft"
        assert row.approved_by is None
        assert row.approved_at is None
        assert row.approval_authority is None
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_denies_flow_for_safe_auto_approval(
    db_session: AsyncSession,
) -> None:
    """Governor ruling 4: a flow-shaped proposal is never eligible for safe
    auto-approval, regardless of how plausible its scope looks."""
    proposal_id = f"test-envelope-flow-{uuid.uuid4().hex[:8]}"
    db_session.add(
        _draft_row(
            proposal_id,
            actions=[
                {
                    "action_id": None,
                    "flow_id": "flow.build_test_for_symbol",
                    "parameters": {"source_file": _ENVELOPE_FILE_PATH},
                    "order": 0,
                }
            ],
            scope={
                "files": [_ENVELOPE_FILE_PATH],
                "modules": [],
                "symbols": [],
                "policies": [],
            },
        )
    )
    await db_session.commit()

    try:
        with pytest.raises(SafeAutoApprovalDeniedError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="autonomous_self_promote",
                approval_authority="risk_classification.safe_auto_approval",
            )

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "draft"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_denies_out_of_envelope_path_for_safe_auto_approval(
    db_session: AsyncSession,
) -> None:
    """Governor ruling 3/5: an in-envelope action targeting a path outside
    src/ or tests/ is still denied."""
    proposal_id = f"test-envelope-path-{uuid.uuid4().hex[:8]}"
    out_of_envelope = ".intent/rules/code/imports.json"
    db_session.add(
        _draft_row(
            proposal_id,
            actions=[
                {
                    "action_id": "fix.format",
                    "parameters": {"file_path": out_of_envelope},
                    "order": 0,
                }
            ],
            scope={
                "files": [out_of_envelope],
                "modules": [],
                "symbols": [],
                "policies": [],
            },
        )
    )
    await db_session.commit()

    try:
        with pytest.raises(SafeAutoApprovalDeniedError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="autonomous_self_promote",
                approval_authority="risk_classification.safe_auto_approval",
            )

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "draft"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_governor_authority_crosses_envelope(
    db_session: AsyncSession,
) -> None:
    """Governor ruling 7: principal.governor approval is NOT bound by the
    safe_auto_approval_envelope — the exact same out-of-envelope proposal
    that #853's other tests prove denies under
    risk_classification.safe_auto_approval succeeds here."""
    proposal_id = f"test-envelope-governor-{uuid.uuid4().hex[:8]}"
    out_of_envelope = ".intent/rules/code/imports.json"
    db_session.add(
        _draft_row(
            proposal_id,
            actions=[
                {
                    "action_id": "check.imports",
                    "parameters": {"file_path": out_of_envelope},
                    "order": 0,
                }
            ],
            scope={
                "files": [out_of_envelope],
                "modules": [],
                "symbols": [],
                "policies": [],
            },
        )
    )
    await db_session.commit()

    try:
        await ProposalStateManager(db_session).approve(
            proposal_id,
            approved_by="cli_admin",
            approval_authority="principal.governor",
        )
        await db_session.commit()

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "approved"
        assert row.approval_authority == "principal.governor"
    finally:
        await _delete(db_session, proposal_id)
