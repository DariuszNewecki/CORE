# tests/cli/logic/interactive_test/steps/test_utils__open_in_editor_async.py

"""open_in_editor_async launches $EDITOR through subprocess_utils.run_child_process."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cli.logic.interactive_test.steps import utils
from cli.logic.interactive_test.steps.utils import open_in_editor_async


async def test_editor_launched_with_inherited_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITOR", "my-editor")
    run = AsyncMock(return_value=0)
    target = tmp_path / "f.py"
    with patch.object(utils, "run_child_process", run):
        assert await open_in_editor_async(target) is True

    run.assert_awaited_once()
    args, kwargs = run.call_args
    assert args == (["my-editor", str(target)],)
    assert kwargs["cwd"] == Path.cwd()
    assert kwargs["env"] == dict(os.environ)


async def test_zero_exit_is_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITOR", "true")
    assert await open_in_editor_async(tmp_path / "f.py") is True


async def test_non_zero_exit_is_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITOR", "false")
    assert await open_in_editor_async(tmp_path / "f.py") is False


async def test_missing_editor_is_failure_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITOR", "no-such-editor-binary-xyz")
    assert await open_in_editor_async(tmp_path / "f.py") is False
