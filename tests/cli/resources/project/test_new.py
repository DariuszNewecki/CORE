# tests/cli/resources/project/test_new.py
"""`core-admin project new` command surface (ADR-119 Amendment 2026-10-02, #892)."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer

from cli.resources.project.new import new_project_command


def _ctx(core_root: Path) -> MagicMock:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = MagicMock()
    ctx.obj.git_service.repo_path = core_root
    return ctx


# ID: bf91737b-ef74-4163-91f3-6947ff2418e1
def test_profile_option_removed_and_path_option_present() -> None:
    params = inspect.signature(new_project_command).parameters
    assert "profile" not in params
    assert "path" in params


# ID: e02b1ae1-db5e-4f89-b77e-17f89d70e16e
async def test_defaults_to_current_directory_and_never_uses_core_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core_root = tmp_path / "core"
    core_root.mkdir()
    work = tmp_path / "elsewhere"
    work.mkdir()
    monkeypatch.chdir(work)

    await new_project_command(_ctx(core_root), "demo", None, True)

    assert (work / "demo" / ".intent").is_dir()
    assert (work / "demo" / "src" / "demo" / "__init__.py").is_file()
    assert not (tmp_path / "demo").exists()  # not a sibling of CORE
