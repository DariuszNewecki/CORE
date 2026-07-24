# tests/cli/resources/demo/test_consequence_chain_cmd.py
"""Exit-code mapping + confirmation gate for `demo consequence-chain` (ADR-155 §5).

Calls the undecorated coroutine (`.__wrapped__`) so the ADR-155 §5 exit-code
contract is exercised without Docker, a database, or a child process — the
orchestration is replaced with a stub returning a chosen ``PhaseResult``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import typer

import cli.resources.demo.consequence_chain as cc


def _ctx(repo_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        obj=SimpleNamespace(git_service=SimpleNamespace(repo_path=str(repo_root)))
    )


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch, tmp_path):
    monkeypatch.setattr(cc.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(
        cc, "settings", SimpleNamespace(CORE_DEMO_STATE_DIR=tmp_path / "state")
    )
    # Confirmation defaults to accepted; individual tests override.
    monkeypatch.setattr(cc, "confirm_action", lambda *a, **k: True)


# The raw coroutine (`.__wrapped__`) does not go through Typer's option
# resolution, so every option must be supplied explicitly with a real value
# (otherwise the parameter is the `typer.OptionInfo` sentinel, not its default).
_CMD_DEFAULTS = {
    "output": None,
    "keep_workspace": False,
    "simulate_confirmation": False,
    "timeout_seconds": None,
}


async def _call_cmd(ctx, **overrides):
    return await cc.consequence_chain_cmd.__wrapped__(ctx, **{**_CMD_DEFAULTS, **overrides})


async def _invoke(monkeypatch, tmp_path, *, result=None, side_effect=None, **kwargs):
    stub = AsyncMock(return_value=result, side_effect=side_effect)
    monkeypatch.setattr(cc, "run_consequence_chain", stub)
    with pytest.raises(typer.Exit) as exc:
        await _call_cmd(_ctx(tmp_path), **kwargs)
    return exc.value, stub


# ── Exit 0 / 64 map from the run verdict ──────────────────────────────────────


# ID: d9a1ade1-9da4-44d4-9b8a-c2f1f08e40b7
async def test_passing_run_exits_zero(monkeypatch, tmp_path, passing_result):
    exc, _ = await _invoke(monkeypatch, tmp_path, result=passing_result)
    assert exc.exit_code == 0


# ID: df64e6a1-6b72-4543-a485-0ce01ff9d826
async def test_failing_run_exits_64(monkeypatch, tmp_path, failing_result):
    exc, _ = await _invoke(monkeypatch, tmp_path, result=failing_result)
    assert exc.exit_code == 64


# ── Exit 130 on interruption (D11) ────────────────────────────────────────────


# ID: 74093cbb-7d40-48a6-95ca-d71cedc7fd06
async def test_interrupt_exits_130(monkeypatch, tmp_path):
    exc, _ = await _invoke(monkeypatch, tmp_path, side_effect=KeyboardInterrupt())
    assert exc.exit_code == 130


# ID: 87801aa8-cf84-48c4-94ec-645918be441c
async def test_cancelled_exits_130(monkeypatch, tmp_path):
    import asyncio

    exc, _ = await _invoke(monkeypatch, tmp_path, side_effect=asyncio.CancelledError())
    assert exc.exit_code == 130


# ── Exit 2 pre-flight failures (scenario did not start) ───────────────────────


# ID: 354e4ee0-270c-4f81-8652-c22e418b24ba
async def test_missing_docker_exits_2_before_running(monkeypatch, tmp_path):
    monkeypatch.setattr(cc.shutil, "which", lambda _name: None)
    stub = AsyncMock()
    monkeypatch.setattr(cc, "run_consequence_chain", stub)
    with pytest.raises(typer.Exit) as exc:
        await _call_cmd(_ctx(tmp_path))
    assert exc.value.exit_code == 2
    stub.assert_not_awaited()


# ID: 8b9f2a94-41a9-4adf-95c0-72bf6def51ca
async def test_bad_output_path_exits_2_before_running(monkeypatch, tmp_path):
    stub = AsyncMock()
    monkeypatch.setattr(cc, "run_consequence_chain", stub)
    with pytest.raises(typer.Exit) as exc:
        await _call_cmd(_ctx(tmp_path), output="/etc/escape.md")
    assert exc.value.exit_code == 2
    stub.assert_not_awaited()


# ── Declining the D9 prompt is a clean no-op (exit 0), nothing created ─────────


# ID: bd2b5692-3c9a-41df-9efa-13fe872be2e0
async def test_declined_confirmation_exits_zero_without_running(monkeypatch, tmp_path):
    monkeypatch.setattr(cc, "confirm_action", lambda *a, **k: False)
    stub = AsyncMock()
    monkeypatch.setattr(cc, "run_consequence_chain", stub)
    with pytest.raises(typer.Exit) as exc:
        await _call_cmd(_ctx(tmp_path))
    assert exc.value.exit_code == 0
    stub.assert_not_awaited()


# ── --simulate-confirmation skips the prompt but still runs ───────────────────


# ID: 47701f0e-7f54-401e-928c-c281172dc0f4
async def test_simulate_confirmation_skips_prompt(monkeypatch, tmp_path, passing_result):
    calls = {"prompted": False}

    def _boom(*a, **k):
        calls["prompted"] = True
        return True

    monkeypatch.setattr(cc, "confirm_action", _boom)
    exc, stub = await _invoke(
        monkeypatch, tmp_path, result=passing_result, simulate_confirmation=True
    )
    assert exc.exit_code == 0
    assert calls["prompted"] is False
    stub.assert_awaited_once()


# ── passing options through to the orchestration ──────────────────────────────


# ID: 1949096d-bf88-42c4-8817-e7709566cb20
async def test_options_forwarded(monkeypatch, tmp_path, passing_result):
    exc, stub = await _invoke(
        monkeypatch,
        tmp_path,
        result=passing_result,
        keep_workspace=True,
        timeout_seconds=42,
    )
    assert exc.exit_code == 0
    _, kwargs = stub.await_args
    assert kwargs["keep_workspace"] is True
    assert kwargs["timeout_seconds"] == 42.0
    assert callable(kwargs["on_identity"])
