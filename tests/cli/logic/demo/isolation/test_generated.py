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
