# tests/cli/test_admin_cli__intent_config_error.py
"""#939: a rules-only .intent/ is a configuration error, not a crash.

ADR-108 D3 (amended 2026-10-05): the machinery floor must be on disk in the
project's .intent/. Without it the bootstrap gate refuses -- and the CLI must
say what is missing and where the bundled floor lives, exit 2, no traceback.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer

from cli import admin_cli
from cli.utils.exit_codes import EXIT_CONFIG_ERROR
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_validator import validate_intent_tree


_STARTER = Path(__file__).resolve().parents[2] / "examples/starter-intent/.intent"


def _rules_only_intent(root: Path) -> Path:
    intent = root / ".intent"
    (intent / "rules").mkdir(parents=True)
    (intent / "enforcement/mappings").mkdir(parents=True)
    shutil.copy(_STARTER / "rules/starter.json", intent / "rules/starter.json")
    shutil.copy(
        _STARTER / "enforcement/mappings/starter.yaml",
        intent / "enforcement/mappings/starter.yaml",
    )
    return intent


def test_rules_only_tree_names_the_floor_and_where_it_lives(tmp_path: Path) -> None:
    intent = _rules_only_intent(tmp_path)

    with pytest.raises(GovernanceError) as excinfo:
        validate_intent_tree(intent, strict=True)

    msg = str(excinfo.value)
    assert ".intent/META does not exist" in msg
    assert "ADR-108 D3" in msg
    floor = msg.split("copy the missing floor files from ")[1].split(" into ")[0]
    assert (Path(floor) / "META/enums.json").is_file()


def test_missing_bootstrap_file_also_names_the_floor(tmp_path: Path) -> None:
    intent = _rules_only_intent(tmp_path)
    (intent / "META").mkdir()

    with pytest.raises(GovernanceError) as excinfo:
        validate_intent_tree(intent, strict=True)

    assert "Bootstrap Contract v0 violated" in str(excinfo.value)
    assert "machinery floor" in str(excinfo.value)


def test_cli_bootstrap_governance_error_exits_2_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admin_cli, "install_rich_log_handler", lambda: None)
    monkeypatch.setattr(admin_cli, "service_registry", MagicMock())
    monkeypatch.setattr(admin_cli.sys, "argv", ["core-admin", "code", "audit"])

    def _refuse(_registry: object) -> None:
        raise GovernanceError(".intent/META does not exist")

    monkeypatch.setattr(admin_cli, "create_core_context", _refuse)
    printed: list[str] = []
    monkeypatch.setattr(
        admin_cli.console, "print", lambda *a, **k: printed.append(str(a[0]))
    )

    ctx = MagicMock(spec=typer.Context)
    ctx.invoked_subcommand = "code"
    with pytest.raises(typer.Exit) as excinfo:
        admin_cli.main(ctx)

    assert excinfo.value.exit_code == EXIT_CONFIG_ERROR
    assert "Configuration error" in printed[0]
    assert ".intent/META does not exist" in printed[0]
