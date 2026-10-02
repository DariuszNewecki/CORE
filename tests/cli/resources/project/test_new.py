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


def test_runs_without_brain_services_or_core_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (2026-10-02): from a plain pip install `project new` crashed with
    "QDRANT_URL is not configured" — the wrapper warmed Qdrant for a file-only
    command — and located CORE by walking up from cwd. Run the real decorated
    command outside an event loop with a registry whose Qdrant warm-up raises
    and no CORE checkout to protect: it must still create the project."""
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = MagicMock()
    ctx.obj.qdrant_service = None
    ctx.obj.registry.get_qdrant_service.side_effect = ValueError(
        "QDRANT_URL is not configured and no client provided."
    )
    monkeypatch.setattr("cli.resources.project.new.core_source_root", lambda: None)
    monkeypatch.chdir(tmp_path)

    new_project_command(ctx, "demo", None, True)

    assert (tmp_path / "demo" / ".intent").is_dir()
    ctx.obj.registry.get_qdrant_service.assert_not_called()
