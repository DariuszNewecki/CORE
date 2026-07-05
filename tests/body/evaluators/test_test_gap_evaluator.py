# tests/body/evaluators/test_test_gap_evaluator.py
"""Tests for TestGapEvaluator (ADR-133 D1/D2)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from body.evaluators.test_gap_evaluator import (
    TestGapEvaluator,
    _extract_public_symbols,
    _extract_tested_names,
)


# ── _extract_public_symbols ──────────────────────────────────────────────────


def test_extract_public_symbols_returns_top_level_functions(tmp_path):
    src = tmp_path / "foo.py"
    src.write_text("def public_fn(a, b): pass\ndef _private(x): pass\n")
    result = _extract_public_symbols(src)
    assert len(result) == 1
    assert result[0].name == "public_fn"
    assert result[0].kind == "function"


def test_extract_public_symbols_returns_top_level_classes(tmp_path):
    src = tmp_path / "bar.py"
    src.write_text("class MyClass:\n    pass\nclass _Hidden:\n    pass\n")
    result = _extract_public_symbols(src)
    assert len(result) == 1
    assert result[0].name == "MyClass"
    assert result[0].kind == "class"


def test_extract_public_symbols_excludes_nested_functions(tmp_path):
    src = tmp_path / "nested.py"
    src.write_text("def outer():\n    def inner(): pass\n    return inner\n")
    result = _extract_public_symbols(src)
    assert len(result) == 1
    assert result[0].name == "outer"


def test_extract_public_symbols_async_function(tmp_path):
    src = tmp_path / "async_fn.py"
    src.write_text("async def fetch(url: str) -> str: ...\n")
    result = _extract_public_symbols(src)
    assert result[0].kind == "function"
    assert "async def" in result[0].signature


def test_extract_public_symbols_raises_on_syntax_error(tmp_path):
    src = tmp_path / "bad.py"
    src.write_text("def broken(\n")
    with pytest.raises(SyntaxError):
        _extract_public_symbols(src)


# ── _extract_public_symbols — class method extraction (ADR-133 D2) ──────────


def test_extract_public_symbols_extracts_class_methods(tmp_path):
    src = tmp_path / "svc.py"
    src.write_text(
        "class MyService:\n"
        "    def execute(self): pass\n"
        "    def validate(self): pass\n"
        "    def _internal(self): pass\n"
    )
    result = _extract_public_symbols(src)
    names = [s.name for s in result]
    assert "MyService" in names
    assert "MyService.execute" in names
    assert "MyService.validate" in names
    assert "MyService._internal" not in names


def test_extract_public_symbols_excludes_dunder_methods(tmp_path):
    src = tmp_path / "svc.py"
    src.write_text(
        "class MyService:\n"
        "    def __init__(self): pass\n"
        "    def __repr__(self): pass\n"
        "    def execute(self): pass\n"
    )
    result = _extract_public_symbols(src)
    names = [s.name for s in result]
    assert "MyService.__init__" not in names
    assert "MyService.__repr__" not in names
    assert "MyService.execute" in names


def test_extract_public_symbols_method_kind(tmp_path):
    src = tmp_path / "svc.py"
    src.write_text("class Foo:\n    def bar(self): pass\n")
    result = _extract_public_symbols(src)
    method = next(s for s in result if s.name == "Foo.bar")
    assert method.kind == "method"


def test_extract_public_symbols_async_method(tmp_path):
    src = tmp_path / "svc.py"
    src.write_text("class Foo:\n    async def run(self): pass\n")
    result = _extract_public_symbols(src)
    method = next(s for s in result if s.name == "Foo.run")
    assert "async def" in method.signature


# ── _extract_tested_names ────────────────────────────────────────────────────


def test_extract_tested_names_basic(tmp_path):
    test_file = tmp_path / "test_foo.py"
    test_file.write_text(
        "def test_public_fn(): assert True\n"
        "def test_another(): assert True\n"
        "def helper(): pass\n"
    )
    names = _extract_tested_names(test_file)
    assert names == {"public_fn", "another"}


def test_extract_tested_names_empty_file(tmp_path):
    test_file = tmp_path / "test_empty.py"
    test_file.write_text("")
    assert _extract_tested_names(test_file) == set()


def test_extract_tested_names_class_based_methods(tmp_path):
    test_file = tmp_path / "test_svc.py"
    test_file.write_text(
        "class TestMyService:\n"
        "    def test_execute(self): assert True\n"
        "    def test_validate(self): assert True\n"
        "    def helper(self): pass\n"
    )
    names = _extract_tested_names(test_file)
    assert "MyService.execute" in names
    assert "MyService.validate" in names
    assert "MyService.helper" not in names


def test_extract_tested_names_mixed_flat_and_class(tmp_path):
    test_file = tmp_path / "test_mixed.py"
    test_file.write_text(
        "def test_top_level(): pass\nclass TestWorker:\n    def test_run(self): pass\n"
    )
    names = _extract_tested_names(test_file)
    assert "top_level" in names
    assert "Worker.run" in names


# ── TestGapEvaluator.execute ─────────────────────────────────────────────────


@pytest.fixture
def repo_root(tmp_path):
    (tmp_path / "src" / "mypkg").mkdir(parents=True)
    (tmp_path / "tests" / "mypkg").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def evaluator(repo_root):
    return TestGapEvaluator(repo_root=repo_root)


@pytest.mark.asyncio
async def test_evaluate_all_symbols_untested(repo_root, evaluator):
    src = repo_root / "src" / "mypkg" / "service.py"
    src.write_text("def alpha(): pass\ndef beta(): pass\n")

    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        return_value="tests/mypkg/service/test_generated.py",
    ):
        result = await evaluator.execute(source_file="src/mypkg/service.py")

    assert result.ok
    assert result.data["gap_count"] == 2
    assert result.data["covered_count"] == 0
    assert {g["name"] for g in result.data["gaps"]} == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_evaluate_partial_coverage(repo_root, evaluator):
    src = repo_root / "src" / "mypkg" / "service.py"
    src.write_text("def alpha(): pass\ndef beta(): pass\n")
    test_dir = repo_root / "tests" / "mypkg" / "service"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_generated.py").write_text("def test_alpha(): assert True\n")

    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        return_value="tests/mypkg/service/test_generated.py",
    ):
        result = await evaluator.execute(source_file="src/mypkg/service.py")

    assert result.ok
    assert result.data["gap_count"] == 1
    assert result.data["covered_count"] == 1
    assert result.data["gaps"][0]["name"] == "beta"


@pytest.mark.asyncio
async def test_evaluate_no_gaps_when_all_covered(repo_root, evaluator):
    src = repo_root / "src" / "mypkg" / "service.py"
    src.write_text("def alpha(): pass\n")
    test_dir = repo_root / "tests" / "mypkg" / "service"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_generated.py").write_text("def test_alpha(): assert True\n")

    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        return_value="tests/mypkg/service/test_generated.py",
    ):
        result = await evaluator.execute(source_file="src/mypkg/service.py")

    assert result.ok
    assert result.data["gap_count"] == 0


@pytest.mark.asyncio
async def test_evaluate_returns_not_ok_for_missing_source(repo_root, evaluator):
    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        return_value="tests/mypkg/missing/test_generated.py",
    ):
        result = await evaluator.execute(source_file="src/mypkg/missing.py")

    assert not result.ok
    assert "not found" in result.data["error"]


@pytest.mark.asyncio
async def test_evaluate_returns_not_ok_for_invalid_path(repo_root, evaluator):
    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        side_effect=ValueError("bad path"),
    ):
        result = await evaluator.execute(source_file="not/a/src/path.py")

    assert not result.ok
    assert "bad path" in result.data["error"]


@pytest.mark.asyncio
async def test_evaluate_includes_class_methods_in_gaps(repo_root, evaluator):
    src = repo_root / "src" / "mypkg" / "service.py"
    src.write_text(
        "class MyService:\n"
        "    def execute(self): pass\n"
        "    def validate(self): pass\n"
        "    def _internal(self): pass\n"
    )

    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        return_value="tests/mypkg/service/test_generated.py",
    ):
        result = await evaluator.execute(source_file="src/mypkg/service.py")

    assert result.ok
    gap_names = {g["name"] for g in result.data["gaps"]}
    assert "MyService" in gap_names
    assert "MyService.execute" in gap_names
    assert "MyService.validate" in gap_names
    assert "MyService._internal" not in gap_names


@pytest.mark.asyncio
async def test_evaluate_class_method_covered_by_test_class(repo_root, evaluator):
    src = repo_root / "src" / "mypkg" / "service.py"
    src.write_text("class MyService:\n    def execute(self): pass\n")
    test_dir = repo_root / "tests" / "mypkg" / "service"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_generated.py").write_text(
        "class TestMyService:\n    def test_execute(self): assert True\n"
    )

    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        return_value="tests/mypkg/service/test_generated.py",
    ):
        result = await evaluator.execute(source_file="src/mypkg/service.py")

    assert result.ok
    gap_names = {g["name"] for g in result.data["gaps"]}
    covered_names = {g["name"] for g in result.data["already_covered"]}
    assert "MyService.execute" in covered_names
    assert "MyService.execute" not in gap_names
