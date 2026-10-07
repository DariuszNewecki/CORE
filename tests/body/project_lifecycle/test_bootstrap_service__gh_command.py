# tests/body/project_lifecycle/test_bootstrap_service__gh_command.py
"""_run_gh_command runs gh through the sanctioned subprocess surface.

Covers the routing onto ``shared.utils.subprocess_utils.run_command``
(governance.dangerous_execution_primitives): a non-zero exit raises
BootstrapError with gh's stderr logged, unless ``ignore_errors``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from body.project_lifecycle import bootstrap_service
from body.project_lifecycle.bootstrap_service import BootstrapError, _run_gh_command
from shared.utils.subprocess_utils import SubprocessResult


_RUN = "body.project_lifecycle.bootstrap_service.run_command"
_WHICH = "body.project_lifecycle.bootstrap_service.shutil.which"


def _result(returncode: int, stderr: str = "") -> SubprocessResult:
    return SubprocessResult(stdout="", stderr=stderr, returncode=returncode)


def test_success_runs_the_command() -> None:
    with (
        patch(_WHICH, return_value="/usr/bin/gh"),
        patch(_RUN, return_value=_result(0)) as run,
    ):
        _run_gh_command(["gh", "label", "list"])
    run.assert_called_once_with(["gh", "label", "list"])


def test_failure_raises_and_logs_stderr() -> None:
    with (
        patch(_WHICH, return_value="/usr/bin/gh"),
        patch(_RUN, return_value=_result(1, "label already exists")),
        patch.object(bootstrap_service.logger, "error") as err,
    ):
        with pytest.raises(BootstrapError, match="Error running gh command"):
            _run_gh_command(["gh", "label", "create", "x"])
    assert err.call_args[0][1] == "label already exists"


def test_failure_ignored_when_requested() -> None:
    with (
        patch(_WHICH, return_value="/usr/bin/gh"),
        patch(_RUN, return_value=_result(1, "boom")),
        patch.object(bootstrap_service.logger, "error") as err,
    ):
        _run_gh_command(["gh", "label", "create", "x"], ignore_errors=True)
    err.assert_not_called()


def test_missing_gh_raises_before_running() -> None:
    with patch(_WHICH, return_value=None), patch(_RUN) as run:
        with pytest.raises(BootstrapError, match="not found"):
            _run_gh_command(["gh", "issue", "list"])
    run.assert_not_called()
