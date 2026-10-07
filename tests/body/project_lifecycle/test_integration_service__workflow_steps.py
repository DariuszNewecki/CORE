# tests/body/project_lifecycle/test_integration_service__workflow_steps.py
"""integrate_changes runs workflow steps through the sanctioned subprocess surface.

Covers the routing onto ``shared.utils.subprocess_utils.run_command_async``
(governance.dangerous_execution_primitives) with real, cheap processes:
stdout logged at INFO, stderr at WARNING, a failing step halts the workflow
unless it ``continues_on_failure``, and the commit happens only on success.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from body.project_lifecycle import integration_service
from body.project_lifecycle.integration_service import (
    IntegrationError,
    integrate_changes,
)


def _context(repo: Path, steps: list[dict]) -> MagicMock:
    ctx = MagicMock()
    ctx.git_service.repo_path = str(repo)
    ctx.git_service.get_staged_files.return_value = ["src/a.py"]
    ctx.settings.load.return_value = {"integration_workflow": steps}
    return ctx


async def test_successful_steps_log_output_and_commit(tmp_path: Path) -> None:
    steps = [{"description": "say", "command": "echo hello"}]
    ctx = _context(tmp_path, steps)
    with patch.object(integration_service.logger, "info") as info:
        await integrate_changes(ctx, "msg")
    assert any(c.args == ("hello",) for c in info.call_args_list)
    ctx.git_service.commit_paths.assert_called_once_with(["src/a.py"], "msg")


async def test_step_runs_in_the_repository(tmp_path: Path) -> None:
    ctx = _context(tmp_path, [{"description": "where", "command": "pwd"}])
    with patch.object(integration_service.logger, "info") as info:
        await integrate_changes(ctx, "msg")
    assert any(c.args == (str(tmp_path),) for c in info.call_args_list)


async def test_stderr_is_logged_as_warning(tmp_path: Path) -> None:
    ctx = _context(tmp_path, [{"description": "ls", "command": "ls no-such-file"}])
    ctx.settings.load.return_value["integration_workflow"][0][
        "continues_on_failure"
    ] = True
    with patch.object(integration_service.logger, "warning") as warning:
        await integrate_changes(ctx, "msg")
    assert warning.call_count == 1
    assert "no-such-file" in warning.call_args[0][0]
    ctx.git_service.commit_paths.assert_called_once()


async def test_failing_step_halts_and_does_not_commit(tmp_path: Path) -> None:
    steps = [
        {"description": "fail", "command": "false"},
        {"description": "never", "command": "echo unreachable"},
    ]
    ctx = _context(tmp_path, steps)
    with patch.object(integration_service.logger, "info") as info:
        with pytest.raises(IntegrationError):
            await integrate_changes(ctx, "msg")
    assert not any(c.args == ("unreachable",) for c in info.call_args_list)
    ctx.git_service.commit_paths.assert_not_called()


async def test_failing_step_with_continue_proceeds(tmp_path: Path) -> None:
    steps = [{"description": "fail", "command": "false", "continues_on_failure": True}]
    ctx = _context(tmp_path, steps)
    await integrate_changes(ctx, "msg")
    ctx.git_service.commit_paths.assert_called_once()
