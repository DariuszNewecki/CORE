# tests/mind/logic/engines/test_contracts_gate__passive_gate_attestation.py
"""Tests for the passive_gate_symbol_attestation check in contracts_gate.

Covers ADR-142 D2: every Class A passive_gate mapping's enforced_by dotted
path must resolve to an existing Python symbol in src/. Tests exercise the
three private helpers directly and the top-level check function via a
minimal AuditorContext mock.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mind.logic.engines.contracts_gate import (
    _check_passive_gate_symbol_attestation,
    _resolve_enforced_by_symbol,
    _symbol_defined_in_file,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_context(repo_root: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.paths.repo_root = repo_root
    return ctx


def _scaffold(
    tmp_path: Path,
    mapping_content: str,
    src_files: dict[str, str] | None = None,
    *,
    mapping_rel: str = "mappings/will/lifecycle.yaml",
) -> Path:
    """Build a minimal repo skeleton.

    Layout::

        <tmp_path>/
          .intent/enforcement/<mapping_rel>   — the mapping YAML under test
          src/<rel_path>.py                   — source files for symbol resolution
    """
    mapping_path = tmp_path / ".intent" / "enforcement" / mapping_rel
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(mapping_content, encoding="utf-8")

    for rel, content in (src_files or {}).items():
        src_file = tmp_path / "src" / rel
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text(content, encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# _symbol_defined_in_file
# ---------------------------------------------------------------------------


# ID: 82ab63e5-9acd-4af2-ac4c-c909fb7e63d5
def test_symbol_defined_class_found(tmp_path: Path) -> None:
    """Class defined at module level → True."""
    py = tmp_path / "mod.py"
    py.write_text("class MyClass:\n    pass\n", encoding="utf-8")
    assert _symbol_defined_in_file("MyClass", py) is True


# ID: d0320320-5e9c-417f-918f-ef3139900eb6
def test_symbol_defined_function_found(tmp_path: Path) -> None:
    """Function defined at module level → True."""
    py = tmp_path / "mod.py"
    py.write_text("async def my_action(**kwargs): ...\n", encoding="utf-8")
    assert _symbol_defined_in_file("my_action", py) is True


# ID: b30806f2-e46e-4c0f-b084-e9d38a139134
def test_symbol_defined_not_found(tmp_path: Path) -> None:
    """Symbol absent from file → False."""
    py = tmp_path / "mod.py"
    py.write_text("class OtherClass:\n    pass\n", encoding="utf-8")
    assert _symbol_defined_in_file("MyClass", py) is False


# ID: f13beb61-be12-49d8-bd42-8a0e7e814feb
def test_symbol_defined_nested_method_found(tmp_path: Path) -> None:
    """Method nested inside a class is found by ast.walk."""
    py = tmp_path / "mod.py"
    py.write_text(
        "class Outer:\n    def approve(self): ...\n", encoding="utf-8"
    )
    assert _symbol_defined_in_file("approve", py) is True


# ---------------------------------------------------------------------------
# _resolve_enforced_by_symbol
# ---------------------------------------------------------------------------


# ID: 7c1eb3af-5870-4d09-8d4c-1434f151a652
def test_resolve_class_at_module(tmp_path: Path) -> None:
    """will.autonomy.state_mgr.MyClass → src/will/autonomy/state_mgr.py :: MyClass."""
    src = tmp_path / "src"
    (src / "will" / "autonomy").mkdir(parents=True)
    (src / "will" / "autonomy" / "state_mgr.py").write_text(
        "class MyClass:\n    pass\n", encoding="utf-8"
    )
    result = _resolve_enforced_by_symbol("will.autonomy.state_mgr.MyClass", src)
    assert result is not None
    assert "MyClass" in result


# ID: 24499f2c-39b4-4038-8ea0-7f0c965faf8d
def test_resolve_function_at_module(tmp_path: Path) -> None:
    """body.atomic.actions.my_fn → src/body/atomic/actions.py :: my_fn."""
    src = tmp_path / "src"
    (src / "body" / "atomic").mkdir(parents=True)
    (src / "body" / "atomic" / "actions.py").write_text(
        "async def my_fn(**kwargs): ...\n", encoding="utf-8"
    )
    result = _resolve_enforced_by_symbol("body.atomic.actions.my_fn", src)
    assert result is not None
    assert "my_fn" in result


# ID: 938245a2-a458-49de-bd8a-6bb6ce753649
def test_resolve_method_on_class_resolves_to_class(tmp_path: Path) -> None:
    """Dotted paths with .method_name after the class resolve via class existence."""
    src = tmp_path / "src"
    (src / "will" / "autonomy").mkdir(parents=True)
    (src / "will" / "autonomy" / "psm.py").write_text(
        "class PSM:\n    def approve(self): ...\n", encoding="utf-8"
    )
    result = _resolve_enforced_by_symbol("will.autonomy.psm.PSM.approve", src)
    assert result is not None
    assert "PSM" in result


# ID: d7c94342-cefa-494a-a4ac-1a66c49fa98d
def test_resolve_missing_file_returns_none(tmp_path: Path) -> None:
    """Path that references a non-existent file → None."""
    src = tmp_path / "src"
    src.mkdir()
    result = _resolve_enforced_by_symbol("body.nonexistent.module.MyClass", src)
    assert result is None


# ID: c14deed5-1ce6-4514-8e32-19b049d01903
def test_resolve_file_exists_but_symbol_absent_returns_none(tmp_path: Path) -> None:
    """File found but symbol not defined in it → None."""
    src = tmp_path / "src"
    (src / "body" / "validators").mkdir(parents=True)
    (src / "body" / "validators" / "lcv.py").write_text(
        "class OtherValidator:\n    pass\n", encoding="utf-8"
    )
    result = _resolve_enforced_by_symbol(
        "body.validators.lcv.LogicConservationValidator", src
    )
    assert result is None


# ID: 2850e2a1-d681-4ae7-b0fa-13abab27ffea
def test_resolve_package_init(tmp_path: Path) -> None:
    """Symbol defined in a package __init__.py is resolved correctly."""
    src = tmp_path / "src"
    pkg = src / "body" / "services" / "my_svc"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "class MyOrchestrator:\n    pass\n", encoding="utf-8"
    )
    result = _resolve_enforced_by_symbol(
        "body.services.my_svc.MyOrchestrator", src
    )
    assert result is not None
    assert "MyOrchestrator" in result


# ---------------------------------------------------------------------------
# _check_passive_gate_symbol_attestation (integration)
# ---------------------------------------------------------------------------

_CLASS_A_MAPPING = """\
mappings:
  my.rule.valid:
    engine: passive_gate
    params:
      attestation_class: "A"
      enforced_by: "body.validators.lcv.LogicConservationValidator"
      enforcement_note: "enforces something"
    scope:
      applies_to:
        - "src/**/*.py"
"""

_CLASS_B_MAPPING = """\
mappings:
  my.rule.write_time:
    engine: passive_gate
    params:
      attestation_class: "B"
      note: "write-time gate — no enforced_by needed"
    scope:
      applies_to: ["tests/**/*.py"]
"""

_CLASS_A_STALE_MAPPING = """\
mappings:
  my.rule.stale:
    engine: passive_gate
    params:
      attestation_class: "A"
      enforced_by: "body.validators.old_module.OldClass"
    scope:
      applies_to:
        - "src/**/*.py"
"""


# ID: 1f22bcdb-7c7e-4c2b-8c97-9514ed5d80ac
def test_class_a_resolves_passes(tmp_path: Path) -> None:
    """Class A entry whose enforced_by resolves to a live symbol → no findings."""
    repo = _scaffold(
        tmp_path,
        mapping_content=_CLASS_A_MAPPING,
        src_files={
            "body/validators/lcv.py": (
                "class LogicConservationValidator:\n    pass\n"
            )
        },
    )
    ctx = _make_context(repo)
    findings = _check_passive_gate_symbol_attestation(
        ctx, {"mappings_root": ".intent/enforcement/mappings", "src_root": "src"}
    )
    assert findings == []


# ID: 3035d922-77ea-4587-a313-c536835fd80b
def test_class_a_stale_reference_produces_finding(tmp_path: Path) -> None:
    """Class A entry whose enforced_by does not resolve → CRITICAL finding."""
    repo = _scaffold(
        tmp_path,
        mapping_content=_CLASS_A_STALE_MAPPING,
        src_files={},  # old_module does not exist
    )
    ctx = _make_context(repo)
    findings = _check_passive_gate_symbol_attestation(
        ctx, {"mappings_root": ".intent/enforcement/mappings", "src_root": "src"}
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.check_id == "governance.passive_gate.enforced_by_must_resolve"
    assert "my.rule.stale" in f.message
    assert "old_module.OldClass" in f.message


def test_class_b_entry_skipped(tmp_path: Path) -> None:
    """Non-Class-A entry (B/C/D) is not verified — no enforced_by to check."""
    repo = _scaffold(tmp_path, mapping_content=_CLASS_B_MAPPING, src_files={})
    ctx = _make_context(repo)
    findings = _check_passive_gate_symbol_attestation(
        ctx, {"mappings_root": ".intent/enforcement/mappings", "src_root": "src"}
    )
    assert findings == []


def test_non_passive_gate_engine_skipped(tmp_path: Path) -> None:
    """Non-passive_gate engine entries are not checked even if they have enforced_by."""
    mapping = """\
mappings:
  some.other.rule:
    engine: runtime_metric
    params:
      enforced_by: "body.validators.missing.Missing"
    scope:
      applies_to: ["src/**/*.py"]
"""
    repo = _scaffold(tmp_path, mapping_content=mapping, src_files={})
    ctx = _make_context(repo)
    findings = _check_passive_gate_symbol_attestation(
        ctx, {"mappings_root": ".intent/enforcement/mappings", "src_root": "src"}
    )
    assert findings == []


def test_multiple_stale_entries_each_produce_finding(tmp_path: Path) -> None:
    """Two stale Class A entries produce two distinct findings."""
    mapping = """\
mappings:
  rule.one:
    engine: passive_gate
    params:
      attestation_class: "A"
      enforced_by: "body.a.Foo"
    scope:
      applies_to: ["src/**/*.py"]
  rule.two:
    engine: passive_gate
    params:
      attestation_class: "A"
      enforced_by: "body.b.Bar"
    scope:
      applies_to: ["src/**/*.py"]
"""
    repo = _scaffold(tmp_path, mapping_content=mapping, src_files={})
    ctx = _make_context(repo)
    findings = _check_passive_gate_symbol_attestation(
        ctx, {"mappings_root": ".intent/enforcement/mappings", "src_root": "src"}
    )
    assert len(findings) == 2
    rule_ids = {f.context["rule_id"] for f in findings}  # type: ignore[index]
    assert rule_ids == {"rule.one", "rule.two"}


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
