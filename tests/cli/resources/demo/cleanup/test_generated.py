from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer


# ID: 85378f31-621b-4eca-82c3-4c79c16f4426
def test_cleanup_cmd() -> None:
    from cli.resources.demo.cleanup import cleanup_cmd

    ctx = MagicMock()
    settings_mock = MagicMock()
    settings_mock.CORE_DEMO_STATE_DIR = MagicMock()

    mock_git_service = MagicMock()
    mock_git_service.marker_checked_resolve = MagicMock(return_value="/tmp/target-run")
    mock_git_service.marker_checked_remove = MagicMock()

    with (
        patch("cli.resources.demo.cleanup.settings", settings_mock),
        patch("cli.resources.demo.cleanup.GitService", mock_git_service),
        patch("cli.resources.demo.cleanup.console") as mock_console,
    ):
        with pytest.raises(typer.Exit) as exc_info:
            import asyncio

            asyncio.run(cleanup_cmd(ctx, run_id="run-123", write=True))

    assert exc_info.value.exit_code == 0
    mock_git_service.marker_checked_resolve.assert_called_once()
    mock_git_service.marker_checked_remove.assert_called_once()
    mock_console.print.assert_called()
