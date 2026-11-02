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


import pytest

from will.governance.coverage_runner import (
    run_and_persist_coverage_batch,
)


@pytest.mark.asyncio
# ID: f52cda23-6d4e-488c-9f65-4ab163d24e3c
async def test_run_and_persist_coverage_batch():
    context = MagicMock()
    context.cognitive_service = MagicMock()
    session = MagicMock()
    run_id = uuid4()

    update_status = AsyncMock()
    remediate = AsyncMock(
        return_value={"status": "completed", "summary": {"total": 1, "ok": 1}}
    )

    with (
        patch(
            "will.governance.coverage_runner._update_coverage_run_status", update_status
        ),
        patch("will.governance.coverage_runner.remediate_batch_by_symbol", remediate),
    ):
        await run_and_persist_coverage_batch(
            context,
            session,
            run_id=run_id,
            batch_priority="high",
            write=True,
        )

    # executed → completed transitions
    assert update_status.await_count == 2
    first_call = update_status.await_args_list[0]
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True

    final_call = update_status.await_args_list[-1]
    assert final_call.args[2] == "completed"
    assert final_call.kwargs.get("finished") is True
    assert final_call.kwargs.get("error") is None
    assert final_call.kwargs.get("result") == {
        "status": "completed",
        "summary": {"total": 1, "ok": 1},
    }

    remediate.assert_awaited_once_with(context, write=True)


from will.governance.coverage_runner import run_and_persist_coverage_generation


# ID: 5a351c41-2169-4d75-8495-6c3aad39815d
async def test_run_and_persist_coverage_generation(tmp_path):
    target = tmp_path / "module.py"
    target.write_text("x = 1\n")

    context = MagicMock()
    context.git_service.repo_path = tmp_path
    context.cognitive_service = MagicMock()

    session = MagicMock()
    run_id = uuid4()

    mock_status = AsyncMock()
    mock_resolve = MagicMock(return_value=target)
    mock_remediate = AsyncMock(return_value={"status": "completed"})

    with (
        patch(
            "will.governance.coverage_runner._update_coverage_run_status", mock_status
        ),
        patch(
            "will.governance.coverage_runner.resolve_contained_source_path",
            mock_resolve,
        ),
        patch(
            "will.governance.coverage_runner.remediate_file_by_symbol", mock_remediate
        ),
    ):
        await run_and_persist_coverage_generation(
            context,
            session,
            run_id=run_id,
            target_file="module.py",
            write=True,
        )

    mock_remediate.assert_awaited_once_with(context, "module.py", write=True)

    calls = mock_status.await_args_list
    assert calls[0].args == (session, run_id, "executing")
    assert calls[0].kwargs == {"started": True}

    final = calls[-1]
    assert final.args == (session, run_id, "completed")
    assert final.kwargs["finished"] is True
    assert final.kwargs["error"] is None
    assert final.kwargs["result"] == {"status": "completed"}


from will.governance.coverage_runner import get_coverage_methods


# ID: 10deab41-92c0-437a-8cda-ec899e375d08
def test_get_coverage_methods():
    context = MagicMock()

    result = get_coverage_methods(context)

    assert isinstance(result, dict)
    assert "methods" in result
    methods = result["methods"]
    assert len(methods) == 2

    ids = [m["id"] for m in methods]
    assert ids == ["legacy", "adaptive"]
    assert methods[0]["name"] == "Legacy coverage generator"
    assert methods[1]["name"] == "Adaptive coverage generator"
    for method in methods:
        assert isinstance(method["description"], str)
        assert method["description"]


import json


# ID: 48299e8c-0bb5-4bc5-9898-697512633b48
def test_get_coverage_history():
    from will.governance.coverage_runner import get_coverage_history

    entries = [{"pct": 10}, {"pct": 20}, {"pct": 30}]
    context = MagicMock()
    context.git_service.repo_path = "/repo"

    resolved_dir = MagicMock()
    history_file = MagicMock()
    history_file.exists.return_value = True
    history_file.read_text.return_value = json.dumps({"entries": entries})
    resolved_dir.__truediv__ = MagicMock(return_value=history_file)

    resolver_instance = MagicMock()
    resolver_instance.reports_dir = resolved_dir

    with patch(
        "shared.path_resolver.PathResolver", return_value=resolver_instance
    ) as mock_resolver:
        result = get_coverage_history(context, limit=2)

    mock_resolver.assert_called_once_with("/repo")
    resolved_dir.__truediv__.assert_called_once_with("coverage_history.json")
    history_file.read_text.assert_called_once_with(encoding="utf-8")
    assert result == {"count": 2, "history": entries[-2:]}
