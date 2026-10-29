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
