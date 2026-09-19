# tests/will/autonomy/test_proposal_lifecycle_no_draft.py
"""#885 — the Proposal lifecycle has no invisible pre-review state.

Before #885, ``proposal_factory`` and every other creation site created
Proposals in ``DRAFT``; the approval queue (``GET /v1/proposals`` →
``ProposalService.list_pending_approval_paginated``) listed only ``PENDING``;
and ``ProposalStateManager.approve()`` accepted ``DRAFT`` directly. An
actionable Proposal could therefore exist without ever being discoverable
through the one surface built to let a human find work awaiting review.

The Governor's settled resolution (#885): delete the ``DRAFT`` member;
creation starts in ``PENDING``. These tests pin that lifecycle:

* the enum has no ``DRAFT`` and no lifecycle path can produce ``"draft"``;
* every creation path (dataclass default, ``from_dict`` default, the
  assisted-lane factory) starts in ``PENDING``;
* a newly created approval-required Proposal is visible in the normal
  approval queue without knowing its id, and can be approved / rejected
  through the normal lifecycle from there;
* no production source references ``ProposalStatus.DRAFT``.

Envelope denial / safe auto-approval semantics for the mapped lane are
covered where they live: tests/body/services/test_proposal_submission_
service_mapped.py and tests/will/workers/test_violation_remediator_*.py.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.lifecycles.proposal import ProposalStatus
from will.autonomy.proposal import Proposal, ProposalAction, ProposalScope
from will.autonomy.proposal_repository import ProposalRepository
from will.autonomy.proposal_service import ProposalService
from will.autonomy.proposal_state_manager import ProposalStateManager


_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"


# ---------------------------------------------------------------------------
# Enum / vocabulary — pure, no DB
# ---------------------------------------------------------------------------


def test_proposal_status_has_no_draft_member() -> None:
    """``DRAFT`` is gone from the lifecycle vocabulary — re-adding it must be
    a deliberate, visible diff, not a silent regression."""
    assert "DRAFT" not in ProposalStatus.__members__
    assert "draft" not in {s.value for s in ProposalStatus}
    with pytest.raises(ValueError):
        ProposalStatus("draft")


def test_pending_is_the_only_pre_approval_state() -> None:
    """No second pre-review state under another name (#885 scope rule 10):
    the states that precede APPROVED are exactly {PENDING}."""
    terminal_or_post_approval = {
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
        ProposalStatus.FINALIZING,
        ProposalStatus.COMPLETED,
        ProposalStatus.FAILED,
        ProposalStatus.REJECTED,
    }
    pre_approval = set(ProposalStatus) - terminal_or_post_approval
    assert pre_approval == {ProposalStatus.PENDING}


def test_proposal_default_status_is_pending() -> None:
    """The dataclass default is the state the approval queue lists."""
    proposal = Proposal(goal="default status", actions=[], scope=ProposalScope())
    assert proposal.status is ProposalStatus.PENDING


def test_from_dict_without_status_defaults_to_pending() -> None:
    """A serialized Proposal missing ``status`` rehydrates as PENDING, never
    a retired value."""
    data = Proposal(goal="roundtrip", actions=[], scope=ProposalScope()).to_dict()
    data.pop("status", None)
    assert Proposal.from_dict(data).status is ProposalStatus.PENDING


def test_from_dict_rejects_legacy_draft_value() -> None:
    """Persisted ``'draft'`` is a migration concern (20260914_885), not a
    value the domain model silently accepts."""
    data = Proposal(goal="legacy", actions=[], scope=ProposalScope()).to_dict()
    data["status"] = "draft"
    with pytest.raises(ValueError):
        Proposal.from_dict(data)


def test_assisted_lane_factory_creates_pending() -> None:
    """ADR-109 human-gated lane proposals are created directly in the
    reviewable state (they were the #885 reproduction's creation site)."""
    from shared.models.validated_remediation_candidate import (
        _CONSTRUCTOR_TOKEN,
        ValidatedRemediationCandidate,
    )
    from will.autonomy.proposal_factory import build_assisted_lane_proposal

    candidate = ValidatedRemediationCandidate(
        candidate_id="cand-885",
        finding_ids=["f-885"],
        rule_ids=["rule.x"],
        patch="--- a/src/x.py\n+++ b/src/x.py\n",
        patch_digest="digest",
        validated_base_sha="abc123",
        production_set=["src/x.py"],
        validation_checks=["sandbox"],
        validation_results={"sandbox": True},
        created_at=datetime.now(UTC),
        _construction_token=_CONSTRUCTOR_TOKEN,
    )
    proposal = build_assisted_lane_proposal(
        candidate, goal="factory status", created_by="test"
    )
    assert proposal.status is ProposalStatus.PENDING
    assert proposal.approval_required is True


def test_no_production_source_references_proposal_status_draft() -> None:
    """Repository-wide guard: no ``src/`` module references the retired
    member or uses ``'draft'`` as a Proposal status literal."""
    assert (_SRC_ROOT / "will" / "autonomy").is_dir(), _SRC_ROOT
    member_refs: list[str] = []
    literal_refs: list[str] = []
    literal = re.compile(r"""status\s*(?:=|==|:)\s*['"]draft['"]""")
    for path in _SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ProposalStatus.DRAFT" in text:
            member_refs.append(str(path.relative_to(_SRC_ROOT)))
        if literal.search(text):
            literal_refs.append(str(path.relative_to(_SRC_ROOT)))
    assert member_refs == [], f"ProposalStatus.DRAFT referenced in: {member_refs}"
    assert literal_refs == [], f"'draft' Proposal status literal in: {literal_refs}"


# ---------------------------------------------------------------------------
# Queue visibility + lifecycle — DB-backed
# ---------------------------------------------------------------------------

pytestmark_db = pytest.mark.integration


def _approval_required_proposal(tag: str) -> Proposal:
    """A moderate-risk proposal: ``file.edit`` requires human approval."""
    file_path = f"src/t885_{tag}.py"
    proposal = Proposal(
        goal=f"#885 queue visibility {tag}",
        actions=[
            ProposalAction(
                action_id="file.edit",
                parameters={"file_path": file_path, "write": True},
                order=0,
            )
        ],
        scope=ProposalScope(files=[file_path]),
        created_by="test_885",
    )
    proposal.compute_risk()
    assert proposal.approval_required is True
    return proposal


async def _cleanup(db_session: AsyncSession, proposal_ids: list[str]) -> None:
    await db_session.rollback()
    await db_session.execute(
        delete(AutonomousProposal).where(
            AutonomousProposal.proposal_id.in_(proposal_ids)
        )
    )
    await db_session.commit()


@pytestmark_db
async def test_new_approval_required_proposal_is_visible_in_queue(
    db_session: AsyncSession,
) -> None:
    """The #885 defect, falsified: a freshly created approval-required
    Proposal is PENDING and appears in the unfiltered approval queue —
    the same query ``GET /v1/proposals`` runs — without knowing its id."""
    tag = uuid.uuid4().hex[:8]
    proposal = _approval_required_proposal(tag)
    try:
        repo = ProposalRepository(db_session)
        proposal_id = await repo.create(proposal)
        await db_session.commit()

        db_session.expire_all()
        service = ProposalService(db_session)
        queued, _has_more, _cursor = await service.list_pending_approval_paginated(
            limit=500
        )
        by_id = {p.proposal_id: p for p in queued}
        assert proposal_id in by_id, (
            "a newly created approval-required Proposal must be discoverable "
            "through the approval queue, not only by id"
        )
        assert by_id[proposal_id].status is ProposalStatus.PENDING
        assert by_id[proposal_id].approval_required is True
        assert by_id[proposal_id].approval_authority is None
    finally:
        await _cleanup(db_session, [proposal.proposal_id])


@pytestmark_db
async def test_queued_proposal_can_be_approved_then_leaves_queue(
    db_session: AsyncSession,
) -> None:
    """From the queue, the governor lane approves PENDING → APPROVED and the
    row leaves the approval queue."""
    tag = uuid.uuid4().hex[:8]
    proposal = _approval_required_proposal(tag)
    try:
        proposal_id = await ProposalRepository(db_session).create(proposal)
        await db_session.commit()

        await ProposalStateManager(db_session).approve(
            proposal_id,
            approved_by="governor@test",
            approval_authority="principal.governor",
        )
        await db_session.commit()

        db_session.expire_all()
        service = ProposalService(db_session)
        fetched = await service.get(proposal_id)
        assert fetched is not None
        assert fetched.status is ProposalStatus.APPROVED
        assert fetched.approval_authority == "principal.governor"
        queued, _, _ = await service.list_pending_approval_paginated(limit=500)
        assert proposal_id not in {p.proposal_id for p in queued}
    finally:
        await _cleanup(db_session, [proposal.proposal_id])


@pytestmark_db
async def test_queued_proposal_can_be_rejected(db_session: AsyncSession) -> None:
    """From the queue, PENDING → REJECTED through the normal lifecycle."""
    tag = uuid.uuid4().hex[:8]
    proposal = _approval_required_proposal(tag)
    try:
        proposal_id = await ProposalRepository(db_session).create(proposal)
        await db_session.commit()

        await ProposalStateManager(db_session).reject(proposal_id, reason="#885 test")

        db_session.expire_all()
        fetched = await ProposalService(db_session).get(proposal_id)
        assert fetched is not None
        assert fetched.status is ProposalStatus.REJECTED
    finally:
        await _cleanup(db_session, [proposal.proposal_id])


# ---------------------------------------------------------------------------
# Persistence compatibility — by inspection (core_test_db has no DDL rights)
# ---------------------------------------------------------------------------

_REPO_ROOT = _SRC_ROOT.parent
_MIGRATION = "20260914_885_retire_draft_proposal_status.sql"


def test_orm_status_check_constraint_matches_enum_vocabulary() -> None:
    """The DB CHECK vocabulary and the Python enum are the same closed set —
    a row can never carry a status the domain model cannot rehydrate."""
    from shared.infrastructure.database.models.autonomous_proposals import (
        AutonomousProposal,
    )

    check = next(
        c
        for c in AutonomousProposal.__table__.constraints
        if getattr(c, "name", None) == "autonomous_proposals_status_check"
    )
    db_vocab = set(re.findall(r"'([a-z_]+)'", str(check.sqltext)))
    assert db_vocab == {s.value for s in ProposalStatus}
    assert (
        AutonomousProposal.__table__.c.status.server_default.arg
        == ProposalStatus.PENDING.value
    )


def test_legacy_draft_rows_are_reconciled_by_ledger_migration() -> None:
    """Existing databases can hold ``status='draft'`` rows (the live DB had
    two). The ledger migration converts them to ``pending`` — the state they
    were always meant to be discoverable in — before tightening the CHECK
    constraint, and is registered in the manifest so ``core-admin database
    migrate --write`` runs it. Verified by inspection of the migration text."""
    path = _REPO_ROOT / "infra" / "scripts" / "migrations" / _MIGRATION
    assert path.is_file(), path
    sql = path.read_text(encoding="utf-8")
    update_pos = sql.find("SET status = 'pending'")
    assert update_pos != -1 and "WHERE status = 'draft'" in sql
    check_pos = sql.find("ADD CONSTRAINT autonomous_proposals_status_check")
    assert check_pos != -1
    assert update_pos < check_pos, "rows must be reconciled before the CHECK tightens"
    check_clause = sql[check_pos:]
    assert "'draft'" not in check_clause
    assert "SET DEFAULT 'pending'" in sql

    manifest = (_REPO_ROOT / "infra" / "migrations" / "manifest.yaml").read_text(
        encoding="utf-8"
    )
    assert f"- {_MIGRATION}" in manifest

    schema = (_REPO_ROOT / "schema.sql").read_text(encoding="utf-8")
    assert "DEFAULT 'draft'::text" not in schema
    assert "ARRAY['draft'::text" not in schema
