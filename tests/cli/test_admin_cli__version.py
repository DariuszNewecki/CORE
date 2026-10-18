# tests/cli/test_admin_cli__version.py
"""#1157 (proof run 3): `core-admin --version` was "No such option" (exit 2);
the only way to see the installed version was `pip show core-runtime`."""

from __future__ import annotations

import importlib.metadata

import pytest
from typer.testing import CliRunner

from cli import admin_cli


@pytest.mark.parametrize("flag", ["--version", "-V"])
# ID: e991fa3b-40f0-4193-99ce-0cff918b6f7c
def test_version_prints_core_runtime_version_without_bootstrap(
    monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    def _no_bootstrap(*_a, **_k):
        raise AssertionError("--version must not build the CORE context")

    monkeypatch.setattr(admin_cli, "create_core_context", _no_bootstrap)
    monkeypatch.setattr(admin_cli.service_registry, "prime", _no_bootstrap)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "9.8.7")

    result = CliRunner().invoke(admin_cli.app, [flag])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "core-runtime 9.8.7"
