"""ContextValidator is the schema; no file is read (#894 seeded live run).

``var/context/schema.yaml`` was untracked in e5611005 and the doctrine
rewrite (87e19929) moved every check into the class -- but kept the file
load, so ContextService could not be constructed on any machine without a
lingering local copy, and CodeGenerationPhase (which constructs it
unguarded) failed every code_modification goal run at RUNTIME. These tests
pin the file-free construction and the doctrine the class encodes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.infrastructure.context.validator import ContextValidator


def _doctrine_packet() -> dict[str, Any]:
    """The shape ContextBuilder.build returns (builder.py, doctrine-aligned)."""
    return {
        "layer_constraints": {"layer": None, "rules": [], "warning": ""},
        "header": {
            "packet_id": "pkt-1",
            "created_at": "2026-09-15T00:00:00+00:00",
            "builder_version": "2.0",
            "privacy": "local_only",
            "mode": "sandbox",
            "goal": "Evaluate the package",
            "trigger": "goal_execution",
        },
        "phase": "runtime",
        "constitution": {},
        "policy": {"remote_allowed": False},
        "constraints": {"applicable_rules": []},
        "evidence": [
            {"name": "mod.py", "item_type": "snippet", "source": "package/mod.py"}
        ],
        "runtime": {},
        "provenance": {"cache_key": "k", "providers": []},
    }


def test_constructs_without_any_file(tmp_path: Path, monkeypatch: Any) -> None:
    """No schema_path parameter, no attribute, nothing read from var/."""
    monkeypatch.chdir(tmp_path)  # nothing under cwd either
    validator = ContextValidator()
    assert not hasattr(validator, "schema_path")
    assert not hasattr(validator, "schema")
    assert not (tmp_path / "var").exists()


def test_doctrine_packet_validates() -> None:
    result = ContextValidator().validate(_doctrine_packet())
    assert result.ok, result.errors
    assert result.validated_data["phase"] == "runtime"


def test_pre_doctrine_required_fields_are_not_demanded() -> None:
    """The deleted file's `problem`/`scope`/`context` list belonged to the old
    packet layout; a doctrine packet carries none of them and must pass."""
    packet = _doctrine_packet()
    assert not {"problem", "scope", "context"} & packet.keys()
    assert ContextValidator().validate(packet).ok


def test_required_sections_are_named_when_missing() -> None:
    packet = _doctrine_packet()
    del packet["header"], packet["phase"], packet["evidence"]
    errors = ContextValidator().validate(packet).errors
    for section in ("header", "phase", "evidence"):
        assert f"Missing required field: {section}" in errors
    # optional object sections are not demanded
    packet = _doctrine_packet()
    for section in ("constitution", "policy", "constraints", "runtime", "provenance"):
        del packet[section]
    assert ContextValidator().validate(packet).ok


def test_context_service_constructs_on_a_bare_project_root(tmp_path: Path) -> None:
    """The production construction site (bootstrap._build_context_service and
    CodeGenerationPhase) -- a bare repo root, no var/context/ anywhere."""
    from shared.infrastructure.context.service import ContextService

    service = ContextService(project_root=str(tmp_path), session_factory=None)
    assert isinstance(service.validator, ContextValidator)
