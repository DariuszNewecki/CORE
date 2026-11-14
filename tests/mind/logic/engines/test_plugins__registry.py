"""ADR-177 D2-D5 (#1339 PR H): plug-in engines in the engine registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.logic.engines.registry import DuplicateEngineIdError, EngineRegistry
from shared.models import AuditSeverity
from shared.path_resolver import PathResolver
from tests.helpers.fake_plugin import ENGINE_SOURCE, install_fake_plugin


_REPO_ROOT = Path(__file__).resolve().parents[4]


def _manifest(package: str, *classes: str, api: str = "1") -> str:
    engines = ", ".join(f'"{package}.engines:{c}"' for c in classes)
    return (
        f'{{"format_version": 1, "core_engine_api": "{api}", "engines": [{engines}]}}'
    )


def _initialize() -> None:
    EngineRegistry.initialize(PathResolver.from_repo(_REPO_ROOT))


def test_a_plugin_engine_enters_through_the_registration_point(
    fresh_engine_registry: type[EngineRegistry],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="hr-one",
        package="hr_one",
        manifest=_manifest("hr_one", "OneGate"),
        files={
            "engines.py": ENGINE_SOURCE.format(
                class_name="OneGate", engine_id="hr_one_gate"
            )
        },
    )
    _initialize()
    assert "hr_one_gate" in fresh_engine_registry._engine_classes
    assert (
        fresh_engine_registry._engine_sources["hr_one_gate"] == "plug-in hr-one 0.1.0"
    )
    assert fresh_engine_registry._engine_sources["regex_gate"] == "built-in"
    assert [p.label for p in fresh_engine_registry._plugins if p.name == "hr-one"] == [
        "hr-one 0.1.0"
    ]
    assert fresh_engine_registry.get("hr_one_gate").engine_id == "hr_one_gate"


def test_a_plugin_engine_with_a_builtin_id_refuses_the_start(
    fresh_engine_registry: type[EngineRegistry],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="hr-clash",
        package="hr_clash",
        manifest=_manifest("hr_clash", "ClashGate"),
        files={
            "engines.py": ENGINE_SOURCE.format(
                class_name="ClashGate", engine_id="regex_gate"
            )
        },
    )
    with pytest.raises(DuplicateEngineIdError) as exc:
        _initialize()
    message = str(exc.value)
    assert "regex_gate" in message
    assert "(built-in)" in message
    assert "(plug-in hr-clash 0.1.0)" in message
    assert "ADR-177 D5" in message


def test_two_plugins_with_one_engine_id_refuse_the_start(
    fresh_engine_registry: type[EngineRegistry],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for dist, package in (("hr-first", "hr_first"), ("hr-second", "hr_second")):
        install_fake_plugin(
            monkeypatch,
            tmp_path / package,
            dist_name=dist,
            package=package,
            manifest=_manifest(package, "SameGate"),
            files={
                "engines.py": ENGINE_SOURCE.format(
                    class_name="SameGate", engine_id="hr_same_gate"
                )
            },
        )
    with pytest.raises(DuplicateEngineIdError) as exc:
        _initialize()
    message = str(exc.value)
    assert "(plug-in hr-first 0.1.0)" in message
    assert "(plug-in hr-second 0.1.0)" in message


async def test_a_skipped_plugin_engine_gives_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fake_plugin(
        monkeypatch,
        tmp_path,
        dist_name="hr-old",
        package="hr_old",
        manifest=_manifest("hr_old", "OldGate", api="2"),
        files={
            "engines.py": ENGINE_SOURCE.format(
                class_name="OldGate", engine_id="hr_old_gate"
            )
        },
    )
    _initialize()
    assert "hr_old_gate" not in fresh_engine_registry._engine_classes
    rule = ExecutableRule(
        rule_id="hr.old", engine="hr_old_gate", params={}, enforcement="blocking"
    )
    findings = await execute_rule(rule, MagicMock())
    assert [(f.check_id, f.severity) for f in findings] == [
        ("hr.old.engine_missing", AuditSeverity.BLOCK)
    ]
