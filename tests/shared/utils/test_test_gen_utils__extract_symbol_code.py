# tests/shared/utils/test_test_gen_utils__extract_symbol_code.py

"""extract_symbol_code — dotted ClassName.method_name extraction fix.

Source: shared.utils.test_gen_utils.extract_symbol_code

Prior behavior only scanned ast.iter_child_nodes(tree) (top-level nodes),
so a dotted "ClassName.method_name" symbol_name never matched anything —
callers fell back to a bare signature comment with no real code, and the
LLM hallucinated the entire method body. Confirmed cause of ~40% of failed
will/workers test-gen attempts (symbol_kind == "method").
"""

from __future__ import annotations

from pathlib import Path

from shared.utils.test_gen_utils import (
    extract_constructor_signature,
    extract_referenced_module_constants,
    extract_symbol_code,
)


_SOURCE = '''\
"""Module docstring."""


def top_level_func(x: int) -> int:
    return x + 1


class Widget:
    """A widget."""

    CLASS_ATTR = 1

    def __init__(self) -> None:
        self.value = 0

    async def run(self) -> None:
        """Run the widget."""
        self.value += 1

    def _private_helper(self) -> None:
        pass


class OtherWidget:
    async def run(self) -> None:
        return None
'''


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "module.py"
    p.write_text(_SOURCE, encoding="utf-8")
    return p


def test_extracts_top_level_function(tmp_path: Path) -> None:
    result = extract_symbol_code(_write(tmp_path), "top_level_func")
    assert result is not None
    assert "def top_level_func(x: int) -> int:" in result
    assert "return x + 1" in result


def test_extracts_top_level_class(tmp_path: Path) -> None:
    result = extract_symbol_code(_write(tmp_path), "Widget")
    assert result is not None
    assert "class Widget:" in result
    assert "async def run(self)" in result


def test_extracts_dotted_method_from_correct_class(tmp_path: Path) -> None:
    """The core fix: a dotted ClassName.method_name symbol_name resolves to
    the method's own source, not None. Two classes define `run` — must
    return Widget's, not OtherWidget's."""
    result = extract_symbol_code(_write(tmp_path), "Widget.run")

    assert result is not None
    assert "async def run(self) -> None:" in result
    assert '"""Run the widget."""' in result
    assert "self.value += 1" in result


def test_extracts_dotted_method_disambiguates_same_method_name_different_class(
    tmp_path: Path,
) -> None:
    result = extract_symbol_code(_write(tmp_path), "OtherWidget.run")
    assert result is not None
    assert "return None" in result
    assert "self.value += 1" not in result


def test_dotted_symbol_missing_class_returns_none(tmp_path: Path) -> None:
    result = extract_symbol_code(_write(tmp_path), "NoSuchClass.run")
    assert result is None


def test_dotted_symbol_missing_method_returns_none(tmp_path: Path) -> None:
    result = extract_symbol_code(_write(tmp_path), "Widget.no_such_method")
    assert result is None


def test_nonexistent_top_level_symbol_returns_none(tmp_path: Path) -> None:
    result = extract_symbol_code(_write(tmp_path), "does_not_exist")
    assert result is None


def test_unreadable_file_returns_none(tmp_path: Path) -> None:
    result = extract_symbol_code(tmp_path / "missing.py", "anything")
    assert result is None


def test_syntax_error_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "broken.py"
    p.write_text("def f(:\n    pass", encoding="utf-8")
    result = extract_symbol_code(p, "f")
    assert result is None


# ── extract_constructor_signature ──────────────────────────────────────────
# Method-level extraction never includes the containing class's __init__ —
# this is the companion extraction that supplies it, so a generated test
# knows how to instantiate a class whose constructor deviates from the
# common no-arg worker pattern (confirmed live: DbSyncWorker.__init__
# requires core_context; two independent LLM generations both guessed
# DbSyncWorker() with no arguments because they never saw otherwise).


def test_extracts_explicit_constructor(tmp_path: Path) -> None:
    result = extract_constructor_signature(_write(tmp_path), "Widget")
    assert result is not None
    assert "def __init__(self) -> None:" in result
    assert "self.value = 0" in result


def test_no_explicit_constructor_returns_none(tmp_path: Path) -> None:
    """OtherWidget has no __init__ of its own — relies on the base class's
    default. That's genuine absence, not an extraction failure."""
    result = extract_constructor_signature(_write(tmp_path), "OtherWidget")
    assert result is None


def test_constructor_missing_class_returns_none(tmp_path: Path) -> None:
    result = extract_constructor_signature(_write(tmp_path), "NoSuchClass")
    assert result is None


def test_constructor_unreadable_file_returns_none(tmp_path: Path) -> None:
    result = extract_constructor_signature(tmp_path / "missing.py", "Widget")
    assert result is None


# ── extract_referenced_module_constants ────────────────────────────────────
# Neither extract_symbol_code nor extract_constructor_signature includes
# module-level names the symbol reads but doesn't define. Confirmed live on
# prompt_extractor_worker.py: the LLM guessed plausible-but-wrong values for
# _ARTIFACT_TYPE and _EXTRACTION_SUB_NAMESPACE because it never saw them.

_CONST_SOURCE = '''\
"""Module docstring."""

_TOP = "top-level-value"
_UNUSED = "not referenced by anything in Gadget"
_COMPUTED = some_call().attr


class Gadget:
    def __init__(self, x: int) -> None:
        self.x = x

    def method_using_const(self) -> str:
        local_var = _TOP
        return local_var

    def method_shadowing(self) -> str:
        """Locally reassigns _TOP before using it — the module-level _TOP
        is irrelevant here since the local binding shadows it."""
        _TOP = "shadowed locally"
        return _TOP

    def method_with_param_shadow(self, _TOP: str) -> str:
        return _TOP

    def method_no_module_refs(self) -> int:
        return len("hello")


def top_level_func() -> str:
    return _COMPUTED
'''


def _write_const(tmp_path: Path) -> Path:
    p = tmp_path / "consts.py"
    p.write_text(_CONST_SOURCE, encoding="utf-8")
    return p


def test_includes_referenced_constant_excludes_unreferenced(tmp_path: Path) -> None:
    result = extract_referenced_module_constants(
        _write_const(tmp_path), "Gadget.method_using_const"
    )
    assert result is not None
    assert '_TOP = "top-level-value"' in result
    assert "_UNUSED" not in result
    assert "_COMPUTED" not in result


def test_extracts_computed_constant_source_not_evaluated(tmp_path: Path) -> None:
    """A non-literal module constant (a call expression) is included as
    source text — the LLM doesn't need the runtime value, just to know
    this name is real and not something to invent."""
    result = extract_referenced_module_constants(
        _write_const(tmp_path), "top_level_func"
    )
    assert result is not None
    assert "_COMPUTED = some_call().attr" in result


def test_local_shadow_excludes_module_level_constant(tmp_path: Path) -> None:
    """A method that reassigns _TOP before reading it doesn't need the
    module-level constant of the same name — the local binding shadows it."""
    result = extract_referenced_module_constants(
        _write_const(tmp_path), "Gadget.method_shadowing"
    )
    assert result is None


def test_parameter_shadow_excludes_module_level_constant(tmp_path: Path) -> None:
    result = extract_referenced_module_constants(
        _write_const(tmp_path), "Gadget.method_with_param_shadow"
    )
    assert result is None


def test_no_module_level_references_returns_none(tmp_path: Path) -> None:
    """Only references a builtin (len) — nothing module-level to surface."""
    result = extract_referenced_module_constants(
        _write_const(tmp_path), "Gadget.method_no_module_refs"
    )
    assert result is None


def test_referenced_constants_missing_symbol_returns_none(tmp_path: Path) -> None:
    result = extract_referenced_module_constants(
        _write_const(tmp_path), "NoSuchClass.method"
    )
    assert result is None


def test_referenced_constants_unreadable_file_returns_none(tmp_path: Path) -> None:
    result = extract_referenced_module_constants(tmp_path / "missing.py", "anything")
    assert result is None
