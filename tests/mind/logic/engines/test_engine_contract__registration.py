"""ADR-176 D3/D4/D5(a) (#1339 PR C): interface version, one registration
point, duplicate ids refused, record engines built once (#1459)."""

from __future__ import annotations

import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import mind.logic.engines.registry as registry_module
from mind.logic import record_contract
from mind.logic.engines.base import CORE_ENGINE_API, BaseEngine, EngineResult
from mind.logic.engines.registry import DuplicateEngineIdError, EngineRegistry


class _EngineA(BaseEngine):
    engine_id = "contract_dup_gate"

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("not called")


class _EngineB(BaseEngine):
    engine_id = "contract_dup_gate"

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("not called")


class _CountingRecordEngine(BaseEngine):
    engine_id = "contract_counting_gate"
    supports_records = True
    built = 0

    def __init__(self) -> None:
        type(self).built += 1

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("not called")

    async def evaluate_record(
        self, record: Any, rule: str, params: dict[str, Any]
    ) -> Any:
        return record_contract.RulePart(
            rule, self.engine_id, self.evidence_class, "pass", ()
        )


# --- D3: interface version ---------------------------------------------------


def test_core_engine_api_is_major_version_1() -> None:
    assert CORE_ENGINE_API == "1"


def test_base_engine_defaults_api_version_to_1() -> None:
    assert BaseEngine.api_version == "1"


def test_every_builtin_engine_is_on_api_version_1(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    versions = {
        engine_id: cls.api_version
        for engine_id, cls in fresh_engine_registry._engine_classes.items()
    }
    assert set(versions.values()) == {"1"}


# --- D4 / D5(a): one registration point, duplicates refused ------------------


def test_register_refuses_a_second_class_with_the_same_id(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._register(_EngineA, default_id="a")
    with pytest.raises(DuplicateEngineIdError) as exc:
        fresh_engine_registry._register(_EngineB, default_id="b")
    message = str(exc.value)
    assert f"{__name__}._EngineA" in message
    assert f"{__name__}._EngineB" in message
    assert "ADR-176 D5(a)" in message
    assert fresh_engine_registry._engine_classes["contract_dup_gate"] is _EngineA


def test_register_accepts_the_same_class_twice(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._register(_EngineA, default_id="a")
    fresh_engine_registry._register(_EngineA, default_id="a_again")
    assert fresh_engine_registry._engine_classes["contract_dup_gate"] is _EngineA


def test_discovery_refuses_to_start_on_a_duplicate_id(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    """A duplicate is not an import failure: it is raised, not logged."""
    modules = {
        "mind.logic.engines.first": types.SimpleNamespace(EngineA=_EngineA),
        "mind.logic.engines.second": types.SimpleNamespace(EngineB=_EngineB),
    }
    found = [(None, "first", False), (None, "second", False)]
    fresh_engine_registry._engine_classes.clear()
    fresh_engine_registry._discovered = False
    with (
        patch.object(registry_module.pkgutil, "iter_modules", return_value=found),
        patch.object(
            registry_module.importlib,
            "import_module",
            side_effect=lambda name, package: modules[f"{package}{name}"],
        ),
        pytest.raises(DuplicateEngineIdError),
    ):
        fresh_engine_registry._discover_engines()


def test_discovery_still_warns_on_a_module_that_fails_to_import(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    """ADR-176 D7 unchanged: an import failure stays a warning."""

    def _import(name: str, package: str) -> Any:
        if name == ".broken":
            raise ImportError("broken module")
        return types.SimpleNamespace(EngineA=_EngineA)

    found = [(None, "broken", False), (None, "good", False)]
    fresh_engine_registry._engine_classes.clear()
    fresh_engine_registry._discovered = False
    with (
        patch.object(registry_module.pkgutil, "iter_modules", return_value=found),
        patch.object(registry_module.importlib, "import_module", side_effect=_import),
    ):
        fresh_engine_registry._discover_engines()
    assert fresh_engine_registry._engine_classes == {"contract_dup_gate": _EngineA}


# --- D3: record engines built at most once (#1459) ---------------------------


def test_record_engine_is_built_once_per_initialization(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes["contract_counting_gate"] = (
        _CountingRecordEngine
    )
    _CountingRecordEngine.built = 0
    first = fresh_engine_registry.record_engine("contract_counting_gate")
    second = fresh_engine_registry.record_engine("contract_counting_gate")
    assert first is second
    assert _CountingRecordEngine.built == 1


async def test_record_path_builds_an_engine_once_for_many_rules(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes["contract_counting_gate"] = (
        _CountingRecordEngine
    )
    _CountingRecordEngine.built = 0
    rules = [
        record_contract.RecordRule(rule_id=f"r{i}", engine="contract_counting_gate")
        for i in range(3)
    ]
    verdict = await record_contract.evaluate({}, rules)
    assert [part.result for part in verdict.parts] == ["pass", "pass", "pass"]
    assert _CountingRecordEngine.built == 1
