# tests/shared/infrastructure/test_db_common__git_commit_sha.py
"""git_commit_sha — git rev-parse via shared.utils.subprocess_utils.run_command,
with the settings.GIT_COMMIT fallback preserved.

Source: shared.infrastructure.repositories.db.common.git_commit_sha
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from shared.infrastructure.repositories.db import common
from shared.utils.subprocess_utils import SubprocessResult


_TARGET = "shared.infrastructure.repositories.db.common.run_command"


# ID: c5cf5e37-2cbd-42cd-a7e7-71341344e76c
def test_returns_git_sha_on_success() -> None:
    sha = "a" * 40
    with patch(
        _TARGET, return_value=SubprocessResult(stdout=sha, stderr="", returncode=0)
    ) as run:
        assert common.git_commit_sha() == sha
    assert run.call_args.args[0] == ["git", "rev-parse", "--verify", "HEAD"]


# ID: 8417470c-1da1-41cc-bc7f-6b6fef4db5b3
def test_falls_back_to_settings_on_nonzero_exit() -> None:
    fake_settings = MagicMock(GIT_COMMIT="  " + "b" * 45 + " ")
    with (
        patch(
            _TARGET,
            return_value=SubprocessResult(
                stdout="", stderr="fatal: not a git repo", returncode=128
            ),
        ),
        patch.object(common, "settings", fake_settings),
    ):
        assert common.git_commit_sha() == "b" * 40


# ID: 8407f5b4-f5f1-4951-abd9-9cab41cdc2e9
def test_falls_back_to_settings_when_git_missing() -> None:
    fake_settings = MagicMock(GIT_COMMIT="")
    with (
        patch(_TARGET, side_effect=FileNotFoundError("git")),
        patch.object(common, "settings", fake_settings),
    ):
        assert common.git_commit_sha() == ""
