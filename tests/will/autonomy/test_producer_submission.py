# tests/will/autonomy/test_producer_submission.py
"""submit_producer_change: one way in for a change not born from a finding
(ADR-168 Amendment 2026-10-10; producer build U7a).

The candidate is built by the real trusted builder from a fake fix_runs row;
the step-0 report and persistence are stand-ins.
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# body.atomic must finish loading before will.autonomy.proposal (registry
# import order; see test_proposal_check_submission).
import body.atomic  # noqa: F401
from shared.models.validated_remediation_candidate import CandidateConstructionError
from will.autonomy.producer_submission import (
    ProducerSubmissionError,
    submit_producer_change,
)


_PATCH = "diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n"
_SHA = hashlib.sha256(_PATCH.encode()).hexdigest()


def _run_row(mode: str = "general") -> dict:
    return {
        "fix_id": "assisted.validate_diff",
        "status": "completed",
        "result": {
            "ok": True,
            "data": {
                "validation_mode": mode,
                "patch_sha256": _SHA,
                "production_set": ["src/x.py"],
                "validated_base_sha": "base-1",
                "validation_results": {"full_audit": True, "tests": True},
                "finding_rules": [],
                "subject_files": [],
            },
        },
    }


def _session_with(row: dict | None):
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = row

    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def _session():
        yield session

    return session, _session


async def _submit(row: dict, **overrides):
    session, factory = _session_with(row)
    created = AsyncMock()
    kwargs = dict(
        patch=_PATCH,
        validation_run_id="00000000-0000-0000-0000-000000000001",
        goal="add a status line",
        anchor_kind="governor_request",
        anchor_refs=["add a status line to the daily report"],
        producer="claude-session:core-darek",
        retires=[],
    )
    kwargs.update(overrides)
    with (
        patch(
            "body.services.validated_candidate_service.service_registry.session",
            factory,
        ),
        patch("will.autonomy.producer_submission.service_registry.session", factory),
        patch(
            "will.autonomy.producer_submission.service_registry.get_cognitive_service",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "will.autonomy.producer_submission.build_step_zero_report",
            AsyncMock(return_value={"look_alikes": {"status": "nothing_new"}}),
        ),
        patch("will.autonomy.proposal_service.ProposalService.create", created),
    ):
        result = await submit_producer_change(**kwargs)
    return result, created, session


# ID: b6c577e1-4f3b-439e-9706-28d76349cde6
async def test_creates_a_pending_proposal_carrying_who_why_and_step_zero() -> None:
    result, created, session = await _submit(_run_row())

    proposal = created.await_args.args[0]
    assert result["status"] == "pending" and result["approval_required"] is True
    assert proposal.approval_required is True and proposal.approved_by is None
    assert proposal.actions[0].action_id == "assisted.apply_diff"
    assert proposal.actions[0].parameters["validated_base_sha"] == "base-1"
    assert proposal.provenance.problem_owner == "governor"
    assert proposal.provenance.producer == "claude-session:core-darek"
    assert proposal.constitutional_constraints["step_zero"] == result["step_zero"]
    assert proposal.validation_results == {"full_audit": True, "tests": True}
    session.commit.assert_awaited_once()


# ID: 7d4fea88-4e2c-461f-89bd-30afcfbee675
async def test_a_finding_anchor_goes_to_the_finding_lane() -> None:
    with pytest.raises(ProducerSubmissionError, match="finding lane"):
        await _submit(_run_row(), anchor_kind="finding", anchor_refs=["f1"])


# ID: 55220131-4e96-4ce9-8ea0-7b28059ce034
async def test_malformed_provenance_is_refused_before_anything_is_read() -> None:
    with pytest.raises(ProducerSubmissionError, match="producer"):
        await _submit(_run_row(), producer=" ")


# ID: c77b54ca-593c-432e-8a76-6b1d35487742
async def test_a_finding_scoped_validation_run_does_not_qualify() -> None:
    with pytest.raises(CandidateConstructionError, match="finding-scoped"):
        await _submit(_run_row(mode="finding"))
