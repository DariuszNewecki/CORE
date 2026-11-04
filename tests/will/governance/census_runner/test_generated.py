from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.governance.census_runner import get_diff


# ID: 8ec7b3ab-3c5b-4cfe-b8be-b73f6b6757aa
def test_get_diff():
    context = MagicMock()
    context.git_service.repo_path = "/tmp/repo"

    latest = MagicMock(name="latest")
    previous = MagicMock(name="previous")

    history = MagicMock()
    history.get_latest_snapshot.return_value = latest
    history.get_previous_snapshot.return_value = previous

    diff_model = MagicMock()
    diff_model.model_dump.return_value = {"added": 1}

    engine = MagicMock()
    engine.compute_diff.return_value = diff_model

    with (
        patch("will.governance.census_runner.CensusHistory", return_value=history),
        patch("will.governance.census_runner.DiffEngine", return_value=engine),
        patch("will.governance.census_runner.FileService") as mock_fs,
    ):
        mock_fs.return_value = MagicMock()
        result = get_diff(context, baseline=None)

    assert result == {
        "available": True,
        "baseline": None,
        "diff": {"added": 1},
    }
    engine.compute_diff.assert_called_once_with(baseline=previous, current=latest)


from will.governance.census_runner import list_baselines


# ID: 0bd07e1f-5b03-4e4f-b236-04889ba85693
def test_list_baselines() -> None:
    repo_path = MagicMock(name="repo_path")
    context = MagicMock(name="context")
    context.git_service.repo_path = repo_path

    baseline_a = MagicMock(name="baseline_a")
    baseline_a.model_dump.return_value = {"name": "b1"}
    baseline_b = MagicMock(name="baseline_b")
    baseline_b.model_dump.return_value = {"name": "b2"}

    with (
        patch("will.governance.census_runner.FileService") as mock_file_service_cls,
        patch("will.governance.census_runner.BaselineManager") as mock_manager_cls,
        patch(
            "will.governance.census_runner._baseline_registry_path"
        ) as mock_registry_path,
    ):
        mock_registry_path.return_value = "registry_path"
        mock_manager = mock_manager_cls.return_value
        mock_manager.list_baselines.return_value = [baseline_a, baseline_b]

        result = list_baselines(context)

    assert result == {
        "count": 2,
        "baselines": [{"name": "b1"}, {"name": "b2"}],
    }
    mock_file_service_cls.assert_called_once_with(repo_path)
    mock_registry_path.assert_called_once_with(repo_path)
    mock_manager_cls.assert_called_once_with(
        "registry_path", mock_file_service_cls.return_value, repo_path
    )
    mock_manager.list_baselines.assert_called_once_with()
    baseline_a.model_dump.assert_called_once_with(mode="json")
    baseline_b.model_dump.assert_called_once_with(mode="json")


# ID: 26b296e4-d01b-4d52-a8a4-6f29d46f5907
def test_create_baseline():
    from will.governance.census_runner import create_baseline

    context = MagicMock()
    fake_repo_root = MagicMock()
    context.git_service.repo_path = fake_repo_root
    context.git_service.get_current_commit = MagicMock(return_value="a" * 40)

    fake_baseline = MagicMock()
    fake_baseline.model_dump = MagicMock(return_value={"name": "my-baseline"})

    mock_manager = MagicMock()
    mock_manager.set_baseline = MagicMock(return_value=fake_baseline)

    mock_history = MagicMock()
    mock_snapshot = MagicMock()
    mock_snapshot.name = "snapshot-001.json"
    mock_history.get_latest_snapshot = MagicMock(return_value=mock_snapshot)
    mock_history.list_snapshots = MagicMock(return_value=[mock_snapshot])

    with (
        patch("will.governance.census_runner.FileService", MagicMock()),
        patch(
            "will.governance.census_runner.BaselineManager",
            MagicMock(return_value=mock_manager),
        ),
        patch(
            "will.governance.census_runner.CensusHistory",
            MagicMock(return_value=mock_history),
        ),
        patch("will.governance.census_runner._baseline_registry_path", MagicMock()),
        patch("will.governance.census_runner._history_dir", MagicMock()),
    ):
        result = create_baseline(context, name="my-baseline")

    assert result == {"name": "my-baseline"}
    mock_manager.set_baseline.assert_called_once()
    call_kwargs = mock_manager.set_baseline.call_args.kwargs
    assert call_kwargs["name"] == "my-baseline"
    assert call_kwargs["snapshot_file"] == "snapshot-001.json"


from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from will.governance.census_runner import run_and_persist_census


@pytest.mark.asyncio
# ID: a0601f8c-161d-4b73-b95d-56b8c21a652c
async def test_run_and_persist_census() -> None:
    run_id = UUID("12345678-1234-5678-1234-567812345678")

    context = MagicMock()
    context.git_service.repo_path = "/tmp/repo"

    session = MagicMock()

    census = MagicMock()
    census.model_dump.return_value = {"files": 3}

    mock_service = MagicMock()
    mock_service.run_census.return_value = census

    with (
        patch("will.governance.census_runner.CensusService", return_value=mock_service),
        patch(
            "will.governance.census_runner._update_census_run_status",
            new=AsyncMock(),
        ) as mock_update,
    ):
        await run_and_persist_census(context, session, run_id=run_id, snapshot=False)

    mock_service.run_census.assert_called_once_with(repo_path="/tmp/repo")

    assert mock_update.await_count == 2
    first_call = mock_update.await_args_list[0]
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True

    last_call = mock_update.await_args_list[-1]
    assert last_call.args[2] == "completed"
    assert last_call.kwargs.get("finished") is True
    assert last_call.kwargs.get("result") == {"files": 3}
