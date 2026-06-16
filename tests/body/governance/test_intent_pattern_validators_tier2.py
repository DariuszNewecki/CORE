"""Tests for #589 Tier 2 — five new test-quality shape validators on
``body.governance.intent_pattern_validators.PatternValidators``.

Each validator is exercised against a synthetic bad case (expected to
trigger one violation) and a clean case (expected to trigger zero).
The validators are pure-AST so we don't need a live import or DB.
"""

from __future__ import annotations

import ast

from body.governance.intent_pattern_validators import PatternValidators


# ---------------------------------------------------------------------------
# 1. check_no_magicmock_on_await
# ---------------------------------------------------------------------------


def test_magicmock_on_await_flags_attribute_assigned_to_magicmock() -> None:
    code = """
from unittest.mock import MagicMock
mock = MagicMock()
mock.fetch = MagicMock()
async def test_x():
    await mock.fetch()
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_magicmock_on_await(tree, code, "test.py")
    assert len(v) == 1
    assert v[0].rule_name == "code.tests.no_magicmock_on_await"
    assert "fetch" in v[0].message


def test_magicmock_on_await_clean_when_asyncmock_used() -> None:
    code = """
from unittest.mock import AsyncMock, MagicMock
mock = MagicMock()
mock.fetch = AsyncMock()
async def test_x():
    await mock.fetch()
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_magicmock_on_await(tree, code, "test.py") == []


def test_magicmock_on_await_clean_when_no_await_in_file() -> None:
    code = """
from unittest.mock import MagicMock
mock = MagicMock()
mock.fetch = MagicMock()
def test_x():
    mock.fetch()
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_magicmock_on_await(tree, code, "test.py") == []


# ---------------------------------------------------------------------------
# 2. check_no_imported_symbol_redeclared
# ---------------------------------------------------------------------------


def test_imported_symbol_redeclared_flags_local_class_shadowing_import() -> None:
    code = """
from foo.bar import Widget

class Widget:
    pass

def test_x():
    assert Widget()
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_imported_symbol_redeclared(tree, "test.py")
    assert len(v) == 1
    assert v[0].rule_name == "code.tests.no_imported_symbol_redeclared"
    assert "Widget" in v[0].message


def test_imported_symbol_redeclared_clean_for_unrelated_local_class() -> None:
    code = """
from foo.bar import Widget

class _LocalHelper:
    pass

def test_x():
    assert Widget()
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_imported_symbol_redeclared(tree, "test.py") == []


# ---------------------------------------------------------------------------
# 3. check_no_placeholder_test_body
# ---------------------------------------------------------------------------


def test_placeholder_body_flags_test_with_no_assertion() -> None:
    code = """
def test_one():
    do_something()
    result = compute()
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_placeholder_test_body(tree, "test.py")
    assert len(v) == 1
    assert v[0].rule_name == "code.tests.no_placeholder_test_body"


def test_placeholder_body_passes_assert_statement() -> None:
    code = """
def test_one():
    assert 1 == 1
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_placeholder_test_body(tree, "test.py") == []


def test_placeholder_body_passes_pytest_raises() -> None:
    code = """
import pytest
def test_one():
    with pytest.raises(ValueError):
        raise ValueError("x")
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_placeholder_test_body(tree, "test.py") == []


def test_placeholder_body_passes_mock_assert_call() -> None:
    code = """
def test_one(mock):
    mock.foo()
    mock.assert_called_once()
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_placeholder_test_body(tree, "test.py") == []


def test_placeholder_body_does_not_flag_non_test_functions() -> None:
    code = """
def helper():
    do_something()

def test_one():
    assert helper()
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_placeholder_test_body(tree, "test.py") == []


# ---------------------------------------------------------------------------
# 4. check_no_global_module_mutation
# ---------------------------------------------------------------------------


def test_global_module_mutation_flags_top_level_assignment() -> None:
    code = """
import yaml
yaml.safe_load = lambda x: {}

def test_x():
    assert True
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_global_module_mutation(tree, "test.py")
    assert len(v) == 1
    assert v[0].rule_name == "code.tests.no_global_module_mutation"
    assert "yaml.safe_load" in v[0].message


def test_global_module_mutation_flags_inside_fixture_body() -> None:
    code = """
import yaml

def fixture_x():
    yaml.safe_load = lambda x: {}
    return None

def test_x():
    assert True
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_global_module_mutation(tree, "test.py")
    assert len(v) == 1


def test_global_module_mutation_clean_when_no_imports() -> None:
    code = """
def test_x():
    assert True
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_global_module_mutation(tree, "test.py") == []


# ---------------------------------------------------------------------------
# 5. check_no_unresolved_free_names
# ---------------------------------------------------------------------------


def test_unresolved_free_names_flags_missing_import() -> None:
    code = """
def test_x():
    mock = MagicMock()
    assert mock is not None
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py")
    assert len(v) == 1
    assert "MagicMock" in v[0].message


def test_unresolved_free_names_clean_when_imported() -> None:
    code = """
from unittest.mock import MagicMock
def test_x():
    mock = MagicMock()
    assert mock is not None
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_unresolved_free_names(tree, "test.py") == []


def test_unresolved_free_names_clean_for_builtins() -> None:
    code = """
def test_x():
    x = list(range(5))
    assert len(x) == 5
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_unresolved_free_names(tree, "test.py") == []


def test_unresolved_free_names_clean_for_function_parameters() -> None:
    code = """
def test_x(mock_qdrant, mock_path_resolver):
    assert mock_qdrant is not None
    assert mock_path_resolver is not None
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_unresolved_free_names(tree, "test.py") == []


# ---------------------------------------------------------------------------
# Integration: validate_test_file_pattern fans out across all 5 + #574
# ---------------------------------------------------------------------------


def test_validate_test_file_pattern_returns_tier2_violations() -> None:
    """A file with multiple shape problems surfaces all of them through
    the public ``validate_test_file_pattern`` entry point."""
    code = """
from unittest.mock import MagicMock
mock = MagicMock()
mock.fetch = MagicMock()

async def test_uses_magicmock_on_await():
    await mock.fetch()

def test_placeholder():
    do_nothing()
"""
    v = PatternValidators.validate_test_file_pattern(code, "test.py")
    rule_names = {report.rule_name for report in v}
    assert "code.tests.no_magicmock_on_await" in rule_names
    assert "code.tests.no_placeholder_test_body" in rule_names
