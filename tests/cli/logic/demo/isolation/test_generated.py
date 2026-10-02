from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cli.logic.demo.isolation import cleanup_run


# ID: 0d3f8d57-58ae-4cde-bb0c-c167b1dec5e8
def test_cleanup_run():
    identity = MagicMock()
    identity.state_dir = Path("/tmp/demo/runs/run-1")
    identity.run_id = "run-1"
    demo_state_dir = Path("/tmp/demo/state")

    with patch(
        "cli.logic.demo.isolation.GitService.marker_checked_remove"
    ) as mock_remove:
        cleanup_run(identity, demo_state_dir)

    mock_remove.assert_called_once_with(
        identity.state_dir, identity.run_id, demo_state_dir
    )


import json

from cli.logic.demo.isolation import read_state_json


# ID: c3dd3d82-a891-4fa4-9382-1d8611f646bb
def test_read_state_json(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    expected = {"status": "ok", "value": 42}
    state_file.write_text(json.dumps(expected), encoding="utf-8")

    result = read_state_json(state_file)

    assert result == expected
