from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from will.governance.refactor_runner import run_and_persist_refactor_autonomous


@pytest.mark.asyncio
# ID: 1c2f59f7-10d6-4681-8fae-2be8a70e837b
async def test_run_and_persist_refactor_autonomous(monkeypatch):
    import will.governance.refactor_runner as rr

    run_id = uuid4()
    goal = "refactor the widget module"
    write = True

    # Fake started_at row result
    started_at_value = "2024-01-01T00:00:00"
    started_at_result = MagicMock()
    started_at_result.first = MagicMock(return_value=(started_at_value,))

    # Fake proposals result
    proposal_row_1 = (str(uuid4()),)
    proposal_row_2 = (str(uuid4()),)
    proposals_result = MagicMock()
    proposals_result.all = MagicMock(return_value=[proposal_row_1, proposal_row_2])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[started_at_result, proposals_result])

    update_mock = AsyncMock()
    monkeypatch.setattr(rr, "_update_refactor_run_status", update_mock)

    develop_mock = AsyncMock(return_value=(True, "all good"))
    monkeypatch.setattr(rr, "develop_from_goal", develop_mock)

    context = MagicMock()

    await run_and_persist_refactor_autonomous(
        context,
        session,
        run_id=run_id,
        goal=goal,
        write=write,
    )

    # develop_from_goal called correctly
    develop_mock.assert_awaited_once()
    _, dev_kwargs = develop_mock.call_args
    assert dev_kwargs["goal"] == goal
    assert dev_kwargs["workflow_type"] == "refactor_modularity"
    assert dev_kwargs["write"] is write

    # Status transitions: executing -> completed
    assert update_mock.await_count == 2
    first_call = update_mock.await_args_list[0]
    assert first_call.args[2] == "executing"

    final_call = update_mock.await_args_list[1]
    assert final_call.args[2] == "completed"
    final_kwargs = final_call.kwargs
    assert final_kwargs["finished"] is True
    assert final_kwargs["error"] is None
    result = final_kwargs["result"]
    assert result["success"] is True
    assert result["message"] == "all good"
    assert result["proposal_count"] == 2
    assert result["proposal_ids"] == [proposal_row_1[0], proposal_row_2[0]]

    assert session.execute.await_count == 2


from pathlib import Path
from unittest.mock import patch


# ID: 9448018e-ff0f-4922-8ced-e4b70df47fee
def test_get_refactor_stats():
    from will.governance.refactor_runner import get_refactor_stats

    fake_files = [Path("/repo/a.py"), Path("/repo/b.py"), Path("/repo/c.py")]
    fake_details = [
        {"total_score": 10.0},
        {"total_score": 45.0},
        {"total_score": 85.0},
    ]

    with (
        patch(
            "will.governance.refactor_runner._enumerate_src_files",
            return_value=fake_files,
        ),
        patch(
            "will.governance.refactor_runner._analyze_one",
            side_effect=fake_details,
        ),
        patch(
            "will.governance.refactor_runner.ModularityChecker",
        ),
    ):
        result = get_refactor_stats(Path("/repo"))

    assert result["count"] == 3
    assert result["max"] == 85.0
    assert result["min"] == 10.0
    assert result["mean"] == (10.0 + 45.0 + 85.0) / 3
    assert result["histogram"] == {
        "0-20": 1,
        "20-40": 0,
        "40-60": 1,
        "60-80": 0,
        "80+": 1,
    }


from will.governance.refactor_runner import get_refactor_candidates


# ID: 2efa2e33-38d4-4e83-9405-5b83965c6037
def test_get_refactor_candidates():
    repo_root = Path("/fake/repo")

    file_a = Path("/fake/repo/src/a.py")
    file_b = Path("/fake/repo/src/b.py")

    # ID: a5fb944b-b5a8-4bc6-97db-39605f47dc71
    def analyze_side_effect(checker, file):
        if file == file_a:
            return {
                "total_score": 2.0,
                "responsibility_count": 3,
                "lines_of_code": 100,
            }
        return {
            "total_score": 5.0,
            "responsibility_count": 4,
            "lines_of_code": 200,
        }

    with (
        patch(
            "will.governance.refactor_runner.get_refactor_threshold",
            return_value=1.5,
        ) as mock_threshold,
        patch(
            "will.governance.refactor_runner.ModularityChecker",
        ) as mock_checker_cls,
        patch(
            "will.governance.refactor_runner._enumerate_src_files",
            return_value=[file_a, file_b],
        ) as mock_enumerate,
        patch(
            "will.governance.refactor_runner._analyze_one",
            side_effect=analyze_side_effect,
        ) as mock_analyze,
    ):
        mock_checker_cls.return_value = MagicMock()

        result = get_refactor_candidates(repo_root)

    mock_threshold.assert_called_once_with(repo_root)
    mock_enumerate.assert_called_once_with(repo_root)
    assert mock_analyze.call_count == 2

    assert result["threshold"] == 1.5
    assert result["count"] == 2
    assert result["candidates"] == [
        {
            "file": "src/b.py",
            "score": 5.0,
            "responsibility_count": 4,
            "lines_of_code": 200,
        },
        {
            "file": "src/a.py",
            "score": 2.0,
            "responsibility_count": 3,
            "lines_of_code": 100,
        },
    ]


from will.governance.refactor_runner import get_refactor_score


# ID: 45222968-e406-4b96-9f97-7c587618526c
def test_get_refactor_score(tmp_path: Path) -> None:
    repo_root = tmp_path
    target = repo_root / "some_file.py"
    target.write_text("def foo():\n    return 1\n", encoding="utf-8")

    fake_details = {
        "total_score": 87.5,
        "file_path": "some_file.py",
    }

    with (
        patch("will.governance.refactor_runner.ModularityChecker") as mock_checker_cls,
        patch(
            "will.governance.refactor_runner._analyze_one",
            return_value=fake_details,
        ) as mock_analyze,
    ):
        mock_checker_cls.return_value = MagicMock()

        result = get_refactor_score(repo_root, "some_file.py")

    assert result["file"] == "some_file.py"
    assert result["found"] is True
    assert result["score"] == 87.5
    assert result["details"] == fake_details
    mock_analyze.assert_called_once()
    args, _ = mock_analyze.call_args
    assert args[1] == target.resolve()




# ID: a47aaf09-a435-4d34-8fbd-4593549aec83
def test_get_refactor_threshold():
    from pathlib import Path

    from will.governance.refactor_runner import get_refactor_threshold

    mock_loader = MagicMock()
    mock_loader.get_enforcement_strategy.return_value = {"params": {"max_score": 42.5}}

    with (
        patch(
            "will.governance.refactor_runner.EnforcementMappingLoader",
            return_value=mock_loader,
        ),
        patch(
            "will.governance.refactor_runner.intent_root_for",
            return_value=Path("/tmp/intent"),
        ) as mock_intent_root,
    ):
        result = get_refactor_threshold(Path("/tmp/repo"))

    assert result == 42.5
    mock_intent_root.assert_called_once_with(Path("/tmp/repo"))
    mock_loader.get_enforcement_strategy.assert_called_once_with(
        "modularity.refactor_score_threshold"
    )
