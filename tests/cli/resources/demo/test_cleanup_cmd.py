# tests/cli/resources/demo/test_cleanup_cmd.py
"""`demo cleanup <run_id>` — marker-checked removal + guard refusal (ADR-155 D11)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

import cli.resources.demo.cleanup as cl
from shared.infrastructure.git_service import DEMO_RUN_MARKER_FILENAME


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(obj=None)


def _make_run(state_root: Path, run_id: str, *, marker: bool = True) -> Path:
    run_dir = state_root / "runs" / run_id
    run_dir.mkdir(parents=True)
    if marker:
        (run_dir / DEMO_RUN_MARKER_FILENAME).write_text(run_id, encoding="utf-8")
    return run_dir


@pytest.fixture(autouse=True)
def _state(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "settings", SimpleNamespace(CORE_DEMO_STATE_DIR=tmp_path))
    return tmp_path


# ID: 262b5992-7cf0-46c9-92a8-2a82889e0f6f
async def test_cleanup_removes_marked_run(_state):
    run_dir = _make_run(_state, "abcdef01")
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="abcdef01")
    assert exc.value.exit_code == 0
    assert not run_dir.exists()


# ID: 7074b693-fd8d-4567-8f18-1ec5cdd68054
async def test_cleanup_missing_run_exits_2(_state):
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="does-not-exist")
    assert exc.value.exit_code == 2


# ID: 118c0426-a4dd-4e17-9258-f0d7b5671e3b
async def test_cleanup_missing_marker_refused(_state):
    run_dir = _make_run(_state, "nomarker0", marker=False)
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="nomarker0")
    assert exc.value.exit_code == 2
    # Guard refused — nothing removed.
    assert run_dir.exists()


# ID: 6c23df2c-73bc-45a5-87d3-33984c7d88ce
async def test_cleanup_unsafe_run_id_refused(_state):
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="../escape")
    assert exc.value.exit_code == 2
