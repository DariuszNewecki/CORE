# tests/cli/resources/demo/test_cleanup_cmd.py
"""`demo cleanup <run_id>` — dry-run vs --write + marker-checked refusal (ADR-155 D11).

ADR-155 Phase 4 (governor-approved): `demo cleanup` stays MUTATE and gains a
`--write` flag. Without `--write` it validates the marker and previews the exact
target but removes nothing; with `--write` it removes, behind the identical
guards. Both modes are covered here.
"""

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


# ── Dry-run (default): previews, removes nothing ──────────────────────────────


# ID: 9aa62842-bf77-40c6-8eab-a9ea964db2e4
async def test_cleanup_dry_run_previews_without_removing(_state):
    run_dir = _make_run(_state, "abcdef01")
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="abcdef01", write=False)
    assert exc.value.exit_code == 0
    # Nothing removed in dry-run.
    assert run_dir.exists()
    assert (run_dir / DEMO_RUN_MARKER_FILENAME).exists()


# ── --write: removes behind the same guards ───────────────────────────────────


# ID: 5aa51fcf-0db0-480b-b715-e234b95e9668
async def test_cleanup_write_removes_marked_run(_state):
    run_dir = _make_run(_state, "abcdef01")
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="abcdef01", write=True)
    assert exc.value.exit_code == 0
    assert not run_dir.exists()


# ── Refusals apply in BOTH modes (validation runs first) ──────────────────────


# ID: e48fc98e-eb8e-4ec9-b75b-e00a4075f206
async def test_cleanup_missing_run_exits_2_dry_run(_state):
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="does-not-exist", write=False)
    assert exc.value.exit_code == 2


# ID: d9563108-ae99-4bc0-beab-7f520f169bc5
async def test_cleanup_missing_marker_refused_even_with_write(_state):
    run_dir = _make_run(_state, "nomarker0", marker=False)
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="nomarker0", write=True)
    assert exc.value.exit_code == 2
    # Guard refused — nothing removed even in --write mode.
    assert run_dir.exists()


# ID: 8cad1332-58f9-4c7f-92e8-ab5636fedbb7
async def test_cleanup_marker_mismatch_refused(_state):
    run_dir = _state / "runs" / "goodname0"
    run_dir.mkdir(parents=True)
    (run_dir / DEMO_RUN_MARKER_FILENAME).write_text("different", encoding="utf-8")
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="goodname0", write=True)
    assert exc.value.exit_code == 2
    assert run_dir.exists()


# ID: e3aa055c-cf80-4a24-8ae9-56c972a57b88
async def test_cleanup_unsafe_run_id_refused(_state):
    with pytest.raises(typer.Exit) as exc:
        await cl.cleanup_cmd.__wrapped__(_ctx(), run_id="../escape", write=True)
    assert exc.value.exit_code == 2
