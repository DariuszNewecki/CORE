"""``core-admin law apply`` refuses outside the custodian account and is dry by default."""

from __future__ import annotations

import inspect

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
