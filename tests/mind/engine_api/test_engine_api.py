"""ADR-177 D1, D6, D7 (#1339 PR G): the public engine interface, its
conformance checks, and the plug-in manifest schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.validators import validator_for

import mind.engine_api as engine_api
from mind.engine_api.conformance import ConformanceProblem, check_engine
from mind.logic import record_contract
from mind.logic.engines import base
from mind.logic.engines.registry import EngineRegistry
from shared.models.audit_models import EvidenceClass
from shared.path_resolver import PathResolver


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA = "plugin_manifest.schema.json"
_SCHEMA_COPIES = [
    _REPO_ROOT / ".intent" / "META" / _SCHEMA,
    _REPO_ROOT / "src" / "shared" / "_machinery_floor" / "META" / _SCHEMA,
    _REPO_ROOT / "examples" / "starter-intent" / ".intent" / "META" / _SCHEMA,
]


# --- D6: the public import path ----------------------------------------------


def test_engine_api_reexports_the_contract_objects() -> None:
    assert engine_api.BaseEngine is base.BaseEngine
    assert engine_api.EngineResult is base.EngineResult
    assert engine_api.normalize_violation is base.normalize_violation
    assert engine_api.CONTENT_NOT_EVALUATED == base.CONTENT_NOT_EVALUATED
    assert engine_api.CORE_ENGINE_API == "1"
    assert engine_api.EvidenceClass is EvidenceClass
    assert engine_api.RulePart is record_contract.RulePart
    assert engine_api.RecordFinding is record_contract.RecordFinding
    assert sorted(engine_api.__all__) == sorted(
        [
            "BaseEngine",
            "CONTENT_NOT_EVALUATED",
            "CORE_ENGINE_API",
            "EngineResult",
            "EvidenceClass",
            "RecordFinding",
            "RulePart",
            "normalize_violation",
        ]
    )


# --- D7: conformance ---------------------------------------------------------


def test_every_builtin_engine_conforms() -> None:
    EngineRegistry.initialize(PathResolver.from_repo(_REPO_ROOT))
    problems = {
        engine_id: [str(p) for p in check_engine(cls)]
        for engine_id, cls in EngineRegistry._engine_classes.items()
    }
    assert len(problems) == 18
    assert {k: v for k, v in problems.items() if v} == {}


class _Good(engine_api.BaseEngine):
    engine_id = "conformance_good_gate"

    async def verify(self, file_path: Path, params: dict[str, Any]) -> Any:
        return None


class _NotAnEngine:
    engine_id = "conformance_plain"


class _SyncVerify(_Good):
    engine_id = "conformance_sync_gate"

    def verify(self, file_path: Path, params: dict[str, Any]) -> Any:  # type: ignore[override]
        return None


class _BadEvidence(_Good):
    engine_id = "conformance_evidence_gate"
    evidence_class = "proven"  # type: ignore[assignment]


class _RecordsWithoutEvaluate(_Good):
    engine_id = "conformance_records_gate"
    supports_records = True


class _SyncEvaluate(_Good):
    engine_id = "conformance_sync_record_gate"
    supports_records = True

    def evaluate_record(self, record: Any, rule: str, params: dict[str, Any]) -> Any:  # type: ignore[override]
        return None


class _Version2(_Good):
    engine_id = "conformance_v2_gate"
    api_version = "2"


class _Unknown(_Good):
    engine_id = "Conformance-Bad"

    def __init__(self, database: Any) -> None:
        pass


def test_a_conforming_engine_has_no_problems() -> None:
    assert check_engine(_Good) == []


@pytest.mark.parametrize(
    ("engine_cls", "expected"),
    [
        (
            _NotAnEngine,
            ConformanceProblem("ADR-176 D2", "is not a subclass of BaseEngine"),
        ),
        (_SyncVerify, ConformanceProblem("ADR-176 D2", "verify is not async")),
        (
            _BadEvidence,
            ConformanceProblem("ADR-176 D2", "evidence_class is not an EvidenceClass"),
        ),
        (
            _RecordsWithoutEvaluate,
            ConformanceProblem(
                "ADR-176 D2",
                "supports_records is True but evaluate_record is not implemented",
            ),
        ),
        (
            _SyncEvaluate,
            ConformanceProblem("ADR-176 D2", "evaluate_record is not async"),
        ),
        (
            _Version2,
            ConformanceProblem(
                "ADR-176 D5(b)", "declares api_version '2'; this CORE supports '1'"
            ),
        ),
    ],
)
def test_each_declaration_problem_is_reported(
    engine_cls: type, expected: ConformanceProblem
) -> None:
    assert check_engine(engine_cls) == [expected]


def test_d6_problems_are_reported() -> None:
    assert check_engine(_Unknown) == [
        ConformanceProblem(
            "ADR-176 D6",
            "engine_id 'Conformance-Bad' is not lowercase letters, digits and underscores",
        ),
        ConformanceProblem(
            "ADR-176 D6", "constructor requires database, which CORE does not inject"
        ),
    ]


# --- D1: the manifest format schema --------------------------------------------


def _validator() -> Any:
    schema = json.loads(_SCHEMA_COPIES[0].read_text(encoding="utf-8"))
    return validator_for(schema)(schema)


def test_schema_ships_in_all_three_places() -> None:
    texts = {path.read_text(encoding="utf-8") for path in _SCHEMA_COPIES}
    assert len(texts) == 1


def test_a_full_manifest_is_valid() -> None:
    manifest = {
        "format_version": 1,
        "core_engine_api": "1",
        "engines": ["example_plugin.engines:ExampleGate"],
        "catalogs": "catalogs",
        "packs": "packs",
    }
    assert list(_validator().iter_errors(manifest)) == []


def test_a_content_only_manifest_is_valid() -> None:
    assert (
        list(
            _validator().iter_errors(
                {"format_version": 1, "core_engine_api": "1", "catalogs": "c"}
            )
        )
        == []
    )


@pytest.mark.parametrize(
    "manifest",
    [
        {"core_engine_api": "1"},
        {"format_version": 1},
        {"format_version": 2, "core_engine_api": "1"},
        {"format_version": 1, "core_engine_api": "1.0"},
        {"format_version": 1, "core_engine_api": "1", "engines": ["no_colon"]},
        {"format_version": 1, "core_engine_api": "1", "name": "not here"},
    ],
)
def test_an_invalid_manifest_is_rejected(manifest: dict[str, Any]) -> None:
    assert list(_validator().iter_errors(manifest)) != []
