"""Tests for ProposalMapper non-ASCII sanitization (#291).

Parent fix 830cc798 wrapped only `execution_results` on the mapper write
paths. #291 confirmed three siblings — `validation_checks`,
`validation_results`, and `constitutional_constraints` — were still
unsanitized at the same lines, and any audit payload carrying em-dashes
or other non-ASCII would hit `asyncpg.UntranslatableCharacterError` on
the SQL_ASCII DB. These tests pin the wrap so a future refactor cannot
silently remove it.
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
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)
from will.autonomy.proposal_mapper import ProposalMapper


pytestmark = [pytest.mark.integration]


def _toxic_proposal(proposal_id: str) -> Proposal:
    """Domain proposal carrying em-dashes, smart quotes, and a NUL byte
    in every field #291 calls out. Mirrors the 830cc798 verification.
    """
    return Proposal(
        proposal_id=proposal_id,
        goal="mapper sanitize test",
        actions=[
            ProposalAction(
                action_id="fix.format",
                parameters={"write": True, "file_path": "src/foo.py"},
                order=0,
            )
        ],
        scope=ProposalScope(files=["src/foo.py"]),
        status=ProposalStatus.DRAFT,
        created_at=datetime.now(UTC),
        validation_checks=[
            "File has 428 lines (limit 400) — consider splitting",
            "smart quote check: “mismatch”",
        ],
        validation_results={"em-dash-check —": True, "ascii-only": False},
        constitutional_constraints={
            "source": "blackboard_findings",
            "rules": [
                "purity.no_todo_placeholders — em-dash in identifier",
            ],
            "narrative": "audit message — with smart quote “foo” and NUL\x00 byte",
            "affected_files_count": 1,
        },
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


async def test_to_db_model_sanitizes_three_sibling_jsonb_fields(
    db_session: AsyncSession,
) -> None:
    """ProposalMapper.to_db_model: validation_checks + validation_results +
    constitutional_constraints all pass through _sanitize_payload before
    the JSONB write, mirroring the existing execution_results wrap.
    """
    proposal_id = f"test-mapper-to-db-{uuid.uuid4().hex[:8]}"
    proposal = _toxic_proposal(proposal_id)

    db_model = ProposalMapper.to_db_model(proposal, AutonomousProposal)
    db_session.add(db_model)
    await db_session.commit()

    try:
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None

        # validation_checks (list[str]): em-dash + smart quote both
        # collapsed to '?'.
        for check in row.validation_checks:
            assert "—" not in check
            assert "“" not in check
            assert "”" not in check
        assert any("?" in c for c in row.validation_checks)

        # constitutional_constraints (dict[str, Any]): string values at
        # every depth replaced; the NUL byte gone.
        cc = row.constitutional_constraints
        assert "—" not in cc["narrative"]
        assert "\x00" not in cc["narrative"]
        assert "“" not in cc["narrative"]
        assert "?" in cc["narrative"]
        for rule in cc["rules"]:
            assert "—" not in rule
        # Non-string values pass through untouched.
        assert cc["affected_files_count"] == 1
    finally:
        await _delete(db_session, proposal_id)


async def test_update_db_model_sanitizes_three_sibling_jsonb_fields(
    db_session: AsyncSession,
) -> None:
    """ProposalMapper.update_db_model: same three fields routed through
    _sanitize_payload on the UPDATE path, so session.flush() cannot
    carry non-ASCII into SQL_ASCII JSONB.
    """
    proposal_id = f"test-mapper-update-{uuid.uuid4().hex[:8]}"

    # Seed a clean draft row first.
    seed = AutonomousProposal(
        proposal_id=proposal_id,
        goal="clean seed",
        status="draft",
        actions=[{"action_id": "fix.format", "parameters": {}, "order": 0}],
        scope={"files": [], "modules": [], "symbols": [], "policies": []},
        validation_checks=[],
        validation_results={},
        constitutional_constraints={},
        approval_required=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(seed)
    await db_session.commit()

    try:
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None

        # Mutate via the mapper UPDATE path with a toxic proposal.
        proposal = _toxic_proposal(proposal_id)
        ProposalMapper.update_db_model(row, proposal)
        await db_session.commit()

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None

        for check in row.validation_checks:
            assert "—" not in check
            assert "“" not in check
        assert any("?" in c for c in row.validation_checks)

        cc = row.constitutional_constraints
        assert "—" not in cc["narrative"]
        assert "\x00" not in cc["narrative"]
        assert "?" in cc["narrative"]
        for rule in cc["rules"]:
            assert "—" not in rule
    finally:
        await _delete(db_session, proposal_id)
