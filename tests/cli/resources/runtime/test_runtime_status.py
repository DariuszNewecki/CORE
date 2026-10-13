# tests/cli/resources/runtime/test_runtime_status.py
"""`core-admin runtime status`: one screen, unreachable sources shown as such."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import cli.resources.runtime.status as status_mod
from cli.resources.runtime import app


def _answers(monkeypatch: pytest.MonkeyPatch, by_suffix: dict[str, object]) -> None:
    async def _get(client, url):
        for suffix, value in by_suffix.items():
            if suffix in url:
                return value
        return None

    monkeypatch.setattr(status_mod, "_get", _get)


def test_shows_the_last_merge_and_what_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "live": "c" * 40,
                "main_head": "c" * 40,
                "state": "idle",
                "last": {"sha": "c" * 40, "result": "live"},
            }
        )
    )
    _answers(
        monkeypatch,
        {
            "/pulls": [{"number": 7, "title": "One-line fix"}],
            "/v1/proposals": {"count": 1},
            "/v1/lane": {"count": 19},
        },
    )
    result = CliRunner().invoke(app, ["status", "--status-file", str(status)])
    assert result.exit_code == 0, result.output
    assert "cccccccccccc live" in result.output
    assert "#7 One-line fix" in result.output
    assert "19" in result.output


def test_unreachable_sources_say_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answers(monkeypatch, {})
    result = CliRunner().invoke(
        app, ["status", "--status-file", str(tmp_path / "missing.json")]
    )
    assert result.exit_code == 0, result.output
    assert "no status file" in result.output
    assert result.output.count("unavailable") == 4  # PRs, proposals, lane, thesis


def test_shows_the_thesis_line_and_what_broke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answers(
        monkeypatch,
        {
            "/v1/thesis": {
                "line": "thesis 2026-10-14: unverified writes 1",
                "breaches": [{"measure": "unverified_writes", "message": "x"}],
                "unavailable": [],
            }
        },
    )
    result = CliRunner().invoke(
        app, ["status", "--status-file", str(tmp_path / "missing.json")]
    )
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "thesis 2026-10-14" in flat
    assert "BROKEN: unverified_writes" in flat.replace("│ ", "").replace(" │", "")
