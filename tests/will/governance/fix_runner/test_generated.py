from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from will.governance.fix_runner import run_and_persist_quality


# ID: 6216af36-3d79-41d1-b022-05a0e507e19f
async def test_run_and_persist_quality():
    context = MagicMock()
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    result_payload = {"ok": True, "summary": "all good"}

    mock_update = AsyncMock()
    mock_lint = AsyncMock(return_value=result_payload)

    with (
        patch("will.governance.fix_runner._update_fix_run_status", mock_update),
        patch("will.governance.fix_runner._run_quality_lint", mock_lint),
    ):
        await run_and_persist_quality(
            context,
            session,
            run_id=run_id,
            check="lint",
            params={"fix": True},
        )

    mock_lint.assert_awaited_once_with(context, fix=True)

    assert mock_update.await_count == 2
    first_call = mock_update.await_args_list[0]
    assert first_call.args[1] == run_id
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True

    second_call = mock_update.await_args_list[1]
    assert second_call.args[1] == run_id
    assert second_call.args[2] == "completed"
    assert second_call.kwargs.get("finished") is True
    assert second_call.kwargs.get("error") is None
    assert second_call.kwargs.get("result") == result_payload



import pytest

from will.governance.fix_runner import run_quality_policy_coverage


@pytest.mark.asyncio
# ID: 61c719b1-beea-4b4a-a31e-f9a19a209e7a
async def test_run_quality_policy_coverage():
    fake_report = MagicMock()
    fake_report.report_id = "rpt-123"
    fake_report.generated_at_utc = "2024-01-01T00:00:00Z"
    fake_report.repo_root = "/repo"
    fake_report.summary = {"total": 3, "covered": 3}
    fake_report.records = [{"policy": "p1", "covered": True}]
    fake_report.exit_code = 0

    context = MagicMock()
    context.git_service.repo_path = "/repo"

    mock_service_cls = MagicMock()
    mock_service_instance = MagicMock()
    mock_service_instance.run.return_value = fake_report
    mock_service_cls.return_value = mock_service_instance

    mock_path_resolver_cls = MagicMock()
    mock_path_resolver_cls.from_repo.return_value = MagicMock()

    with (
        patch(
            "mind.governance.policy_coverage_service.PolicyCoverageService",
            mock_service_cls,
        ),
        patch("shared.path_resolver.PathResolver", mock_path_resolver_cls),
        patch(
            "will.governance.fix_runner.intent_root_for", return_value="/repo/intents"
        ),
    ):
        result = await run_quality_policy_coverage(context)

    assert result == {
        "report_id": "rpt-123",
        "generated_at_utc": "2024-01-01T00:00:00Z",
        "repo_root": "/repo",
        "summary": {"total": 3, "covered": 3},
        "records": [{"policy": "p1", "covered": True}],
        "exit_code": 0,
    }
    mock_path_resolver_cls.from_repo.assert_called_once_with(
        repo_root="/repo", intent_root="/repo/intents"
    )
    mock_service_instance.run.assert_called_once_with()
