"""`core-admin plugin list | check` (#1339 PR J, ADR-177 D7, D8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from cli.resources.plugin import app as plugin_app
from cli.resources.plugin.check import run_check
from tests.helpers.fake_plugin import ENGINE_SOURCE, install_fake_plugin


ROOT = typer.Typer()
ROOT.add_typer(plugin_app, name="plugin")


def _install(
    monkeypatch: pytest.MonkeyPatch, site: Path, dist: str, manifest: str
) -> None:
    package = dist.replace("-", "_")
    install_fake_plugin(
        monkeypatch,
        site,
        dist_name=dist,
        package=package,
        manifest=manifest.replace("PKG", package),
        files={
            "engines.py": ENGINE_SOURCE.format(
                class_name="CliGate", engine_id=f"{package}_gate"
            )
        },
    )


_GOOD = (
    '{"format_version": 1, "core_engine_api": "1", "engines": ["PKG.engines:CliGate"]}'
)


def test_list_shows_an_installed_plugin_as_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, tmp_path, "jc-listed", _GOOD)
    result = CliRunner().invoke(ROOT, ["plugin", "list", "--format", "json"])
    assert result.exit_code == 0, result.output
    (row,) = [r for r in json.loads(result.output) if r["name"] == "jc-listed"]
    assert row["engines"] == ["jc_listed_gate"]
    assert row["fingerprint"].startswith("sha256:")


async def test_check_a_conforming_plugin_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Through run_check, not CliRunner: typer's runner closes its own output
    # buffer when a full check runs inside it under pytest's capture.
    _install(monkeypatch, tmp_path, "jc-good", _GOOD)
    code, text = await run_check("jc-good", "text")
    assert code == 0, text
    assert text.splitlines()[0] == "Plug-in jc-good 0.1.0: conforms"
    assert "Problems: none" in text


def test_check_a_broken_plugin_exits_1_with_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(
        monkeypatch, tmp_path, "jc-bad", '{"format_version": 1, "core_engine_api": "2"}'
    )
    result = CliRunner().invoke(ROOT, ["plugin", "check", "jc-bad", "--format", "json"])
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    assert data["loaded"] is False
    assert data["problems"][0]["rule"] == "ADR-177 D4"


def test_check_an_unknown_plugin_exits_3() -> None:
    result = CliRunner().invoke(ROOT, ["plugin", "check", "jc-not-installed"])
    assert result.exit_code == 3
