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


def test_an_applied_proposal_is_refused_before_anything_is_read_or_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """#1096: law apply refuses an id that already has a ledger line."""
    import json

    import cli.resources.law.apply as apply_mod

    ledger = tmp_path / "custody" / "ledger.jsonl"
    ledger.parent.mkdir()
    ledger.write_text(
        json.dumps(
            {
                "proposal": "0018-d2-release-runtime",
                "approved_utc": "2026-10-15T09:22:47Z",
                "approver": "auto:record-only",
            }
        )
        + "\n"
    )
    monkeypatch.setenv("CORE_CUSTODY_LEDGER", str(ledger))
    monkeypatch.setattr(apply_mod, "require_custodian", lambda env: "core-law")
    monkeypatch.setattr(apply_mod, "get_repo_root", lambda start: tmp_path)
    prepared: list[str] = []

    def _prepare(**kw):
        prepared.append(kw["proposal_id"])
        raise apply_mod.ProposalError("stop here")

    monkeypatch.setattr(apply_mod, "prepare", _prepare)

    result = CliRunner().invoke(app, ["apply", "0018-d2-release-runtime", "--write"])
    assert result.exit_code == 1
    assert "already applied" in result.output
    assert (
        "2026-10-15T09:22:47Z" in result.output and "auto:record-only" in result.output
    )
    assert prepared == []  # refused before the proposal was even read

    # An id with no ledger line goes on to be prepared as before.
    CliRunner().invoke(app, ["apply", "0037-new"])
    assert prepared == ["0037-new"]
