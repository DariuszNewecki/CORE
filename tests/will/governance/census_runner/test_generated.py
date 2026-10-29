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
