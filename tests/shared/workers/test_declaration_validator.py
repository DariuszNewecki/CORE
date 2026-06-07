# tests/shared/workers/test_declaration_validator.py

"""
Tests for shared.workers.declaration_validator (issue #460).

Covers:
  - every shipped .intent/workers/*.yaml validates cleanly
  - structural violations rejected (missing fields, bad phase value)
  - fail-closed on missing/empty `worker_phase` enum in enums.json
  - $ref resolution into enums.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from shared.infrastructure.intent.canonical_enums import reload_enums_cache
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.processors.yaml_processor import strict_yaml_processor
from shared.workers.declaration_validator import (
    reset_worker_validator_cache,
    validate_worker_declaration,
)


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    """Reset per-process caches between tests."""
    reset_worker_validator_cache()
    reload_enums_cache()
    yield
    reset_worker_validator_cache()
    reload_enums_cache()


def _minimal_valid_declaration() -> dict[str, Any]:
    return {
        "$schema": "META/worker.schema.json",
        "kind": "worker",
        "metadata": {
            "id": "workers.test_dummy",
            "title": "Test Dummy",
            "version": "1.0",
            "authority": "policy",
            "status": "active",
        },
        "identity": {
            "uuid": "12345678-1234-1234-1234-123456789012",
            "class": "sensing",
        },
        "mandate": {
            "responsibility": "A test responsibility sentence with no conjunctions.",
            "phase": "audit",
            "scope": {
                "artifact_type": ["python"],
                "rule_namespace": "test.dummy",
            },
        },
        "implementation": {
            "module": "will.workers.dummy",
            "class": "DummyWorker",
        },
    }


def test_all_shipped_worker_yamls_validate() -> None:
    """Every declaration under .intent/workers/ must pass the canonical schema."""
    repo = get_intent_repository()
    workers_dir = repo.resolve_rel("workers")
    failures: list[tuple[Path, str]] = []
    yaml_files = sorted(workers_dir.glob("*.yaml"))
    assert yaml_files, "No worker YAMLs found — workers/ directory is empty?"
    for path in yaml_files:
        data = strict_yaml_processor.load_strict(path)
        try:
            validate_worker_declaration(data, source=path)
        except GovernanceError as e:
            failures.append((path, str(e)))
    assert not failures, "Worker declarations failed schema validation:\n" + "\n".join(
        f"  {p}: {msg}" for p, msg in failures
    )


def test_valid_declaration_passes() -> None:
    validate_worker_declaration(_minimal_valid_declaration())


def test_invalid_phase_value_rejected() -> None:
    """`phase: interpret` is in the full `phase` enum but not in `worker_phase`."""
    decl = _minimal_valid_declaration()
    decl["mandate"]["phase"] = "interpret"
    with pytest.raises(GovernanceError) as excinfo:
        validate_worker_declaration(decl)
    assert "phase" in str(excinfo.value)


def test_unknown_phase_value_rejected() -> None:
    decl = _minimal_valid_declaration()
    decl["mandate"]["phase"] = "not_a_real_phase"
    with pytest.raises(GovernanceError):
        validate_worker_declaration(decl)


def test_missing_phase_rejected() -> None:
    decl = _minimal_valid_declaration()
    del decl["mandate"]["phase"]
    with pytest.raises(GovernanceError):
        validate_worker_declaration(decl)


def test_missing_required_top_level_rejected() -> None:
    decl = _minimal_valid_declaration()
    del decl["identity"]
    with pytest.raises(GovernanceError):
        validate_worker_declaration(decl)


def test_extra_properties_rejected() -> None:
    decl = _minimal_valid_declaration()
    decl["mandate"]["rogue_field"] = "not allowed"
    with pytest.raises(GovernanceError):
        validate_worker_declaration(decl)


def test_worker_phase_missing_from_enums_raises_governance_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `worker_phase` is removed from enums.json, validator construction must fail closed."""
    repo = get_intent_repository()
    enums_path = repo.resolve_rel("META/enums.json")
    enums_doc = json.loads(enums_path.read_text("utf-8"))
    enums_doc["definitions"].pop("worker_phase", None)
    patched_enums = tmp_path / "enums.json"
    patched_enums.write_text(json.dumps(enums_doc), encoding="utf-8")

    real_resolve = repo.resolve_rel

    def fake_resolve(rel: str | Path) -> Path:
        if str(rel) == "META/enums.json":
            return patched_enums
        return real_resolve(rel)

    monkeypatch.setattr(repo, "resolve_rel", fake_resolve)
    reset_worker_validator_cache()
    reload_enums_cache()

    with pytest.raises(GovernanceError) as excinfo:
        validate_worker_declaration(_minimal_valid_declaration())
    assert "worker_phase" in str(excinfo.value)


def test_worker_phase_empty_raises_governance_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `worker_phase.enum` is empty `[]`, validator construction must fail closed."""
    repo = get_intent_repository()
    enums_path = repo.resolve_rel("META/enums.json")
    enums_doc = json.loads(enums_path.read_text("utf-8"))
    enums_doc["definitions"]["worker_phase"]["enum"] = []
    patched_enums = tmp_path / "enums.json"
    patched_enums.write_text(json.dumps(enums_doc), encoding="utf-8")

    real_resolve = repo.resolve_rel

    def fake_resolve(rel: str | Path) -> Path:
        if str(rel) == "META/enums.json":
            return patched_enums
        return real_resolve(rel)

    monkeypatch.setattr(repo, "resolve_rel", fake_resolve)
    reset_worker_validator_cache()
    reload_enums_cache()

    with pytest.raises(GovernanceError) as excinfo:
        validate_worker_declaration(_minimal_valid_declaration())
    msg = str(excinfo.value)
    assert "worker_phase" in msg and "empty" in msg
