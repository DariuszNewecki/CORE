"""ADR-176 D5(b) and D6 (#1339 PR D): refusal of an unsupported interface
version, the warn-now checks, and the public ``engine_class`` lookup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.logic.engines.base import BaseEngine, EngineResult
from mind.logic.engines.passive_gate import PassiveGateEngine
from mind.logic.engines.registry import EngineRegistry
from shared.models import AuditSeverity
from shared.path_resolver import PathResolver


_REPO_ROOT = Path(__file__).resolve().parents[4]


class _Engine(BaseEngine):
    engine_id = "contract_check_gate"

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("not called")


def _adr176(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "ADR-176" in r.getMessage()]


# --- No warning for CORE's own engines -----------------------------------------


def test_builtin_engines_give_no_adr176_warning(
    fresh_engine_registry: type[EngineRegistry], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    fresh_engine_registry.initialize(PathResolver.from_repo(_REPO_ROOT))
    assert _adr176(caplog) == []
    assert len(fresh_engine_registry._engine_classes) == 18


# --- D5(b): unsupported api_version is refused ----------------------------------


class _Version2Engine(_Engine):
    engine_id = "contract_v2_gate"
    api_version = "2"


def test_unsupported_api_version_is_not_registered_and_warns(
    fresh_engine_registry: type[EngineRegistry], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    fresh_engine_registry._register(_Version2Engine, default_id="v2")
    assert "contract_v2_gate" not in fresh_engine_registry._engine_classes
    (message,) = _adr176(caplog)
    assert "contract_v2_gate" in message
    assert "'2'" in message
    assert "supports '1'" in message
    assert "ADR-176 D5(b)" in message


async def test_rule_naming_a_refused_engine_gives_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._register(_Version2Engine, default_id="v2")
    rule = ExecutableRule(
        rule_id="contract.v2",
        engine="contract_v2_gate",
        params={},
        enforcement="blocking",
    )
    findings = await execute_rule(rule, MagicMock())
    assert [(f.check_id, f.severity) for f in findings] == [
        ("contract.v2.engine_missing", AuditSeverity.BLOCK)
    ]


def test_api_version_1_is_registered_without_warning(
    fresh_engine_registry: type[EngineRegistry], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    fresh_engine_registry._register(_Engine, default_id="x")
    assert fresh_engine_registry._engine_classes["contract_check_gate"] is _Engine
    assert _adr176(caplog) == []


# --- D6: warnings in 3.x; the engine is still registered ------------------------


class _NoIdEngine(BaseEngine):
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("not called")


class _BadFormatEngine(_Engine):
    engine_id = "Contract-Bad"


class _AliasEngine(_Engine):
    engine_id = "advisory"


class _UnknownParamEngine(_Engine):
    engine_id = "contract_param_gate"

    def __init__(self, path_resolver: Any, database: Any) -> None:
        raise AssertionError("not built")


@pytest.mark.parametrize(
    ("engine_cls", "registered_id", "expected"),
    [
        (_NoIdEngine, "contract_no_id", "no explicit engine_id"),
        (
            _BadFormatEngine,
            "Contract-Bad",
            "not lowercase letters, digits and underscores",
        ),
        (_AliasEngine, "advisory", "is also a passive alias"),
        (_UnknownParamEngine, "contract_param_gate", "requires database"),
    ],
)
def test_d6_problem_warns_and_still_registers(
    fresh_engine_registry: type[EngineRegistry],
    caplog: pytest.LogCaptureFixture,
    engine_cls: type,
    registered_id: str,
    expected: str,
) -> None:
    caplog.set_level(logging.WARNING)
    fresh_engine_registry._register(engine_cls, default_id="contract_no_id")
    assert fresh_engine_registry._engine_classes[registered_id] is engine_cls
    (message,) = _adr176(caplog)
    assert registered_id in message
    assert expected in message
    assert "ADR-176 D6" in message


# --- engine_class: the public lookup rule_extractor uses ------------------------


def test_engine_class_returns_the_class_without_building_it(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._instances.clear()
    cls = fresh_engine_registry.engine_class("passive_gate")
    assert cls is PassiveGateEngine
    assert fresh_engine_registry._instances == {}


def test_engine_class_resolves_a_passive_alias(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    assert fresh_engine_registry.engine_class("advisory") is PassiveGateEngine


def test_engine_class_is_none_for_an_unknown_id(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    assert fresh_engine_registry.engine_class("contract_no_such_gate") is None
