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


import pytest

from will.governance.coverage_runner import get_coverage_gaps


@pytest.mark.asyncio
# ID: aae3ea1f-bbf5-4165-875d-02a3f1904a12
async def test_get_coverage_gaps():
    mocked_context = MagicMock()
    mocked_context.git_service.repo_path = "/repo/root"

    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.get_module_coverage = AsyncMock(
        return_value={
            "src/a.py": 50.0,
            "src/b.py": 90.0,
            "src/c.py": 60.0,
            "src/d.py": 75.0,
        }
    )

    with patch(
        "will.governance.coverage_runner.CoverageAnalyzer",
        return_value=mock_analyzer_instance,
    ):
        result = await get_coverage_gaps(mocked_context, threshold=75.0, limit=20)

    mock_analyzer_instance.get_module_coverage.assert_awaited_once_with()
    assert result["threshold"] == 75.0
    assert result["count"] == 2
    assert result["gaps"] == [
        {"file": "src/a.py", "coverage": 50.0, "deficit": 25.0},
        {"file": "src/c.py", "coverage": 60.0, "deficit": 15.0},
    ]


from pathlib import Path


# ID: 524da227-c344-4ab5-8356-55ad2c8d7842
def test_get_coverage_targets():
    from will.governance.coverage_runner import get_coverage_targets

    mock_repo = MagicMock()
    mock_repo.root = Path("/mind")
    mock_repo.load_document = MagicMock(return_value={"statement": 90, "branch": 85})

    mock_context = MagicMock()

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        result = get_coverage_targets(mock_context)

    assert result["path"] == str(
        Path(".intent") / "enforcement" / "config" / "test_coverage.yaml"
    )
    assert result["targets"] == {"statement": 90, "branch": 85}
    mock_repo.initialize.assert_called_once()
    mock_repo.load_document.assert_called_once_with(
        mock_repo.root / "enforcement" / "config" / "test_coverage.yaml"
    )


import asyncio

from will.governance.coverage_runner import get_coverage_html_report


# ID: a8bbb4de-eb13-4593-a6c2-cb297ef59b1f
def test_get_coverage_html_report() -> None:
    context = MagicMock()

    result = asyncio.run(get_coverage_html_report(context))

    assert result["ok"] is False
    assert result["exit_code"] == -1
    assert result["html_path"] is None
    assert result["stdout_tail"] == []
    assert result["stderr_tail"] == []
    assert isinstance(result["summary"], str)
    assert "ADR-132 D10.10" in result["summary"]


import pytest

from will.governance.coverage_runner import get_coverage_report


@pytest.mark.asyncio
# ID: 0e8153ab-64e3-4c2a-9cd4-e904bd5c1479
async def test_get_coverage_report():
    context = MagicMock()
    context.git_service.repo_path = "/repo/path"

    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.exit_code = 0
    fake_result.status = "passed"
    fake_result.reason = "all good"
    fake_result.stderr = "line1\nline2"
    fake_result.coverage = {
        "text": "Name    Stmts   Miss\nfoo.py   10   0\nbar.py   5   2"
    }

    with patch(
        "body.sandbox.repo_tests.run_in_sandbox",
        new=AsyncMock(return_value=fake_result),
    ) as mock_run:
        out = await get_coverage_report(context, show_missing=True)

    mock_run.assert_awaited_once_with("/repo/path", ["tests"], coverage=True)
    assert out["ok"] is True
    assert out["exit_code"] == 0
    assert out["summary"] == "passed: all good"
    assert out["stdout_tail"] == [
        "Name    Stmts   Miss",
        "foo.py   10   0",
        "bar.py   5   2",
    ]
    assert out["stderr_tail"] == ["line1", "line2"]



import pytest

from will.governance.coverage_runner import get_coverage_check


@pytest.mark.asyncio
# ID: bc0d6322-96f7-4416-b9f7-3ed8aa9d13a3
async def test_get_coverage_check():
    context = MagicMock()
    auditor_ctx = MagicMock()
    auditor_ctx.load_knowledge_graph = AsyncMock(return_value=None)
    context.auditor_context = auditor_ctx

    finding = MagicMock()
    finding.as_dict = MagicMock(
        return_value={"file": "a.py", "rule_id": "coverage.test_coverage_required"}
    )

    run_filtered_audit = AsyncMock(
        return_value=(
            [finding],
            {"coverage.test_coverage_required"},
            {"files_scanned": 1},
        )
    )

    with patch(
        "will.governance.coverage_runner.run_filtered_audit",
        run_filtered_audit,
    ):
        result = await get_coverage_check(context)

    auditor_ctx.load_knowledge_graph.assert_awaited_once()
    run_filtered_audit.assert_awaited_once()
    assert result["verdict"] == "FAIL"
    assert result["passed"] is False
    assert result["finding_count"] == 1
    assert result["findings"] == [
        {"file": "a.py", "rule_id": "coverage.test_coverage_required"}
    ]
    assert result["executed_rule_ids"] == ["coverage.test_coverage_required"]
    assert result["stats"] == {"files_scanned": 1}
