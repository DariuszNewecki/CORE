from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.governance.coverage_runner import run_tests_interactive


# ID: d55ed5e9-4c0d-41af-a27a-d9e001f5ecc8
async def test_run_tests_interactive() -> None:
    fixed_repo_root = "/repo/root"

    mock_git_service = MagicMock()
    mock_git_service.repo_path = fixed_repo_root

    context = MagicMock()
    context.git_service = mock_git_service
    context.cognitive_service = MagicMock()

    mock_file_path = MagicMock()
    mock_file_path.exists.return_value = True
    mock_file_path.is_file.return_value = True

    expected_result = {"ok": True, "tests_generated": 1}

    with (
        patch(
            "will.governance.coverage_runner.remediate_file_by_symbol",
            new=AsyncMock(return_value=expected_result),
        ) as mock_remediate_file,
        patch(
            "will.governance.coverage_runner.resolve_contained_source_path",
            return_value=mock_file_path,
        ),
    ):
        result = await run_tests_interactive(context, target_file="src/example.py")

    assert result == expected_result
    mock_remediate_file.assert_awaited_once_with(context, "src/example.py", write=True)


from uuid import uuid4

import pytest

from will.governance.coverage_runner import run_and_persist_coverage_report


@pytest.mark.asyncio
# ID: d89db9f8-6913-4969-a43b-941b958f7f3c
async def test_run_and_persist_coverage_report():
    context = AsyncMock()
    session = AsyncMock()
    run_id = uuid4()

    fake_result = {"ok": True, "summary": "all good"}

    with (
        patch(
            "will.governance.coverage_runner._update_coverage_run_status",
            new=AsyncMock(),
        ) as mock_update,
        patch(
            "will.governance.coverage_runner.get_coverage_report",
            new=AsyncMock(return_value=fake_result),
        ) as mock_get_report,
        patch(
            "will.governance.coverage_runner.get_coverage_html_report",
            new=AsyncMock(),
        ) as mock_get_html,
    ):
        await run_and_persist_coverage_report(
            context,
            session,
            run_id=run_id,
            format="text",
            show_missing=True,
        )

    mock_get_report.assert_awaited_once_with(context, show_missing=True)
    mock_get_html.assert_not_awaited()

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
    payload = second_call.kwargs.get("result")
    assert payload["format"] == "text"
    assert payload["show_missing"] is True
    assert payload["ok"] is True



import pytest

from will.governance.coverage_runner import get_latest_coverage_report


@pytest.mark.asyncio
# ID: 87e6363a-080a-4a32-9f0f-7d41c716a3c1
async def test_get_latest_coverage_report():
    payload = {"format": "text", "coverage": 87.5}
    row = (payload,)

    session = MagicMock()
    result = MagicMock()
    result.first.return_value = row
    session.execute = AsyncMock(return_value=result)

    out = await get_latest_coverage_report(session)

    assert out == payload
    session.execute.assert_awaited_once()
    result.first.assert_called_once()
