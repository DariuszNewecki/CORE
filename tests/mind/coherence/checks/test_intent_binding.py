# tests/mind/coherence/checks/test_intent_binding.py
"""Unit tests for IntentBindingCheck (CCC F-06 scope gap).

Constructs minimal .intent/ and src/ trees in tmp_path and verifies the
check emits candidates for broken bindings and stays silent for valid ones.
No DB, no LLM.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from mind.coherence.checks.intent_binding import (
    IntentBindingCheck,
    _extract_enforced_by,
    _symbol_in_file,
)


def _run(check: IntentBindingCheck) -> list:
    return asyncio.get_event_loop().run_until_complete(check.run())


def _write_phase(phases_dir: Path, name: str, implementation: str) -> Path:
    phases_dir.mkdir(parents=True, exist_ok=True)
    path = phases_dir / f"{name}.yaml"
    path.write_text(yaml.dump({"implementation": implementation}), encoding="utf-8")
    return path


def _write_mapping(mappings_dir: Path, name: str, enforced_by: str) -> Path:
    mappings_dir.mkdir(parents=True, exist_ok=True)
    path = mappings_dir / f"{name}.yaml"
    data = {"mappings": {"some.rule": {"engine": "passive_gate", "params": {"enforced_by": enforced_by}}}}
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


def _write_src(src_dir: Path, module_parts: list[str], symbol: str) -> Path:
    """Write a minimal src file containing the symbol name."""
    *dirs, filename = module_parts
    file_dir = src_dir
    for d in dirs:
        file_dir = file_dir / d
    file_dir.mkdir(parents=True, exist_ok=True)
    src_file = file_dir / f"{filename}.py"
    src_file.write_text(f"class {symbol}: pass\n", encoding="utf-8")
    return src_file


class TestIntentBindingCheck:
    def test_emits_for_missing_module(self, tmp_path: Path) -> None:
        phases_dir = tmp_path / ".intent" / "phases"
        _write_phase(phases_dir, "audit", "will.phases.audit_phase.AuditPhase")
        # src file does NOT exist
        check = IntentBindingCheck(repo_root=tmp_path)
        candidates = _run(check)
        assert len(candidates) == 1
        assert "INTENT_BINDING" == candidates[0].relation
        assert "no source file found" in candidates[0].claim

    def test_emits_for_missing_symbol(self, tmp_path: Path) -> None:
        phases_dir = tmp_path / ".intent" / "phases"
        _write_phase(phases_dir, "audit", "will.phases.audit_phase.AuditPhase")
        # File exists but does NOT contain the symbol
        src_file = tmp_path / "src" / "will" / "phases" / "audit_phase.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("class OtherClass: pass\n", encoding="utf-8")
        check = IntentBindingCheck(repo_root=tmp_path)
        candidates = _run(check)
        assert len(candidates) == 1
        assert "AuditPhase" in candidates[0].claim
        assert "not found" in candidates[0].claim

    def test_silent_for_valid_implementation(self, tmp_path: Path) -> None:
        phases_dir = tmp_path / ".intent" / "phases"
        _write_phase(phases_dir, "audit", "will.phases.audit_phase.AuditPhase")
        _write_src(tmp_path / "src", ["will", "phases", "audit_phase"], "AuditPhase")
        check = IntentBindingCheck(repo_root=tmp_path)
        candidates = _run(check)
        assert candidates == []

    def test_silent_for_valid_enforced_by(self, tmp_path: Path) -> None:
        mappings_dir = tmp_path / ".intent" / "enforcement" / "mappings"
        _write_mapping(mappings_dir, "test_mapping", "body.services.my_service.MyClass")
        _write_src(tmp_path / "src", ["body", "services", "my_service"], "MyClass")
        check = IntentBindingCheck(repo_root=tmp_path)
        candidates = _run(check)
        assert candidates == []

    def test_enforced_by_with_prose_suffix(self, tmp_path: Path) -> None:
        """'SomeClass enum' suffix should be stripped; only the dotted path is checked."""
        mappings_dir = tmp_path / ".intent" / "enforcement" / "mappings"
        _write_mapping(mappings_dir, "test_mapping", "shared.cli.command_meta.CommandBehavior enum")
        _write_src(tmp_path / "src", ["shared", "cli", "command_meta"], "CommandBehavior")
        check = IntentBindingCheck(repo_root=tmp_path)
        candidates = _run(check)
        assert candidates == []

    def test_resolves_via_init(self, tmp_path: Path) -> None:
        """Module that is a package (__init__.py) should resolve correctly."""
        phases_dir = tmp_path / ".intent" / "phases"
        _write_phase(phases_dir, "load", "will.phases.LoadPhase")
        pkg = tmp_path / "src" / "will" / "phases"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("class LoadPhase: pass\n", encoding="utf-8")
        check = IntentBindingCheck(repo_root=tmp_path)
        candidates = _run(check)
        assert candidates == []


class TestExtractEnforcedBy:
    def test_extracts_flat(self) -> None:
        data = {"params": {"enforced_by": "a.b.C"}}
        assert _extract_enforced_by(data) == ["a.b.C"]

    def test_extracts_nested(self) -> None:
        data = {"mappings": {"rule1": {"params": {"enforced_by": "x.Y"}}, "rule2": {"params": {"enforced_by": "z.W"}}}}
        result = _extract_enforced_by(data)
        assert set(result) == {"x.Y", "z.W"}

    def test_ignores_non_string(self) -> None:
        data = {"enforced_by": 42}
        assert _extract_enforced_by(data) == []

    def test_empty(self) -> None:
        assert _extract_enforced_by({}) == []


class TestSymbolInFile:
    def test_found(self, tmp_path: Path) -> None:
        f = tmp_path / "f.py"
        f.write_text("class MyClass: pass\n")
        assert _symbol_in_file(f, "MyClass") is True

    def test_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "f.py"
        f.write_text("class Other: pass\n")
        assert _symbol_in_file(f, "MyClass") is False

    def test_missing_file(self, tmp_path: Path) -> None:
        assert _symbol_in_file(tmp_path / "missing.py", "Anything") is False
