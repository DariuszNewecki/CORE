"""``core-admin law apply`` refuses outside the custodian account and is dry by default."""

from __future__ import annotations

import inspect

import pytest
from typer.testing import CliRunner

from cli.resources.law import app
from cli.resources.law.apply import law_apply


def test_refuses_when_not_running_as_core_law() -> None:
    result = CliRunner().invoke(app, ["apply", "0001-x", "--write"])
    assert result.exit_code == 1
    assert "runs only as core-law" in result.output


def test_is_dangerous_with_a_write_flag_defaulting_off() -> None:
    meta = law_apply.__command_meta__  # type: ignore[attr-defined]
    assert meta.dangerous is True
    write = inspect.signature(law_apply).parameters["write"]
    assert write.default.default is False


def test_outside_a_repository_refuses_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 2026-10-12: run from outside the tree, get_repo_root raised
    # FileNotFoundError and the custodian saw a traceback.
    import cli.resources.law.apply as apply_mod

    monkeypatch.setattr(apply_mod, "require_custodian", lambda env: "darek")
    monkeypatch.setattr(
        apply_mod,
        "get_repo_root",
        lambda start: (_ for _ in ()).throw(FileNotFoundError()),
    )
    result = CliRunner().invoke(app, ["apply", "0001-x"])
    assert result.exit_code == 1
    assert "REFUSED" in result.output and "--repo" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
