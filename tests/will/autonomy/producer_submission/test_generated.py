from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.autonomy.producer_submission import submit_producer_change


@pytest.mark.asyncio
# ID: 92e2e130-1a99-45a9-9cd6-637e9586f8c9
async def test_submit_producer_change():
    candidate = MagicMock()
    candidate.production_set = {"src/foo.py", "src/bar.py"}

    step_zero = {"report": "ok"}

    provenance_problems = MagicMock(return_value=[])
    proposal_mock = MagicMock()
    proposal_mock.proposal_id = "prop-123"
    proposal_mock.status = MagicMock()
    proposal_mock.status.value = "pending"
    proposal_mock.compute_risk = MagicMock()
    proposal_mock.check_submission = MagicMock(return_value=[])

    fake_provenance = MagicMock()
    fake_provenance.retires = []
    fake_provenance.problems = provenance_problems

    session = AsyncMock()
    session.commit = AsyncMock()

    session_ctx = MagicMock()
    session_ctx.__aenter__ = AsyncMock(return_value=session)
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    service_registry_mock = MagicMock()
    service_registry_mock.session = MagicMock(return_value=session_ctx)
    service_registry_mock.get_cognitive_service = AsyncMock(return_value=MagicMock())

    bootstrap_registry_mock = MagicMock()
    bootstrap_registry_mock.get_repo_path = MagicMock(return_value="/repo")

    proposal_service_instance = MagicMock()
    proposal_service_instance.create = AsyncMock()

    with (
        patch(
            "will.autonomy.producer_submission.build_validated_candidate",
            AsyncMock(return_value=candidate),
        ),
        patch(
            "will.autonomy.producer_submission.build_step_zero_report",
            AsyncMock(return_value=step_zero),
        ),
        patch(
            "will.autonomy.producer_submission.build_general_proposal",
            MagicMock(return_value=proposal_mock),
        ),
        patch(
            "will.autonomy.producer_submission.ProposalProvenance",
            MagicMock(return_value=fake_provenance),
        ),
        patch(
            "will.autonomy.producer_submission.service_registry",
            service_registry_mock,
        ),
        patch(
            "will.autonomy.producer_submission.bootstrap_registry",
            bootstrap_registry_mock,
        ),
        patch(
            "will.autonomy.proposal_service.ProposalService",
            MagicMock(return_value=proposal_service_instance),
        ),
    ):
        result = await submit_producer_change(
            patch="diff --git ...",
            validation_run_id="run-1",
            goal="make it better",
            anchor_kind="patch",
            anchor_refs=["ref-a"],
            producer="tester",
        )

    assert result["proposal_id"] == "prop-123"
    assert result["status"] == "pending"
    assert result["approval_required"] is True
    assert sorted(result["scope_files"]) == ["src/bar.py", "src/foo.py"]
    assert result["step_zero"] == step_zero

    proposal_mock.compute_risk.assert_called_once()
    proposal_mock.check_submission.assert_called_once()
    proposal_service_instance.create.assert_awaited_once_with(proposal_mock)
    session.commit.assert_awaited_once()


import pytest

from will.autonomy.producer_submission import ProducerSubmissionError


# ID: d1ac07f0-1ab7-4b5a-aba8-b56f47df3b9f
def test_ProducerSubmissionError():
    message = "the submission is not acceptable"
    with pytest.raises(ProducerSubmissionError) as exc_info:
        raise ProducerSubmissionError(message)
    assert str(exc_info.value) == message
    assert isinstance(exc_info.value, ValueError)
