"""Tests for #589 Tier 2 — five new test-quality shape validators on
``body.governance.intent_pattern_validators.PatternValidators``.

Each validator is exercised against a synthetic bad case (expected to
trigger one violation) and a clean case (expected to trigger zero).
The validators are pure-AST so we don't need a live import or DB.
"""

from __future__ import annotations

import ast

import pytest

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
    assert v[0].rule_name == "code.tests.no_unresolved_free_names"
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


# Valid Python the hand-rolled binding collector used to reject: every name
# below is bound by the compiler's own scoping rules (2026-10-03 — the
# knowledge_source_check.py generations were rejected for 'rule_id'/'self').
_BOUND_BY_SCOPING = {
    "generator_target": """
def test_x():
    ids = ["a"]
    assert all(rule_id for rule_id in ids)
""",
    "list_comprehension_target": """
def test_x():
    assert [item * 2 for item in range(3)]
""",
    "set_comprehension_target": """
def test_x():
    assert {entry for entry in range(3)}
""",
    "dict_comprehension_targets": """
def test_x():
    assert {k: v for k, v in [("a", 1)]}
""",
    "lambda_param": """
def test_x():
    f = lambda rule_id: rule_id
    assert f(1)
""",
    "nested_def_params": """
def test_x():
    def verify_async(self, rule_id):
        return [self, rule_id]
    assert verify_async(1, 2)
""",
    "walrus": """
def test_x():
    if (n := 3) > 2:
        assert n
""",
    "match_capture": """
def test_x():
    match [1, 2, 3]:
        case [first, *rest]:
            assert first and rest
""",
    "class_body_names": """
class TestK:
    base = 1
    derived = base + 1

    def test_m(self):
        assert self.derived
""",
    "global_declared_in_function": """
def _set():
    global counter
    counter = 1

def test_x():
    _set()
    assert counter == 1
""",
    "nonlocal": """
def test_x():
    hits = 0
    def bump():
        nonlocal hits
        hits += 1
    bump()
    assert hits == 1
""",
    # Evaluated in the enclosing scope (shapes from existing repo tests that
    # an earlier draft of the fail-closed check refused).
    "lambda_in_decorator": """
import pytest

@pytest.mark.parametrize("mutate", [lambda b: b.pop("k"), lambda b: b.clear()])
def test_x(mutate):
    assert mutate
""",
    "generator_in_decorator": """
import pytest

@pytest.mark.parametrize("n", sorted(p for p in range(3)))
def test_x(n):
    assert n >= 0
""",
    "lambda_default": """
def test_x(f=lambda v: v):
    assert f(1)
""",
    "comprehension_iterable_uses_outer_name": """
def test_x():
    ids = [1]
    assert all(i for i in ids)
""",
}


@pytest.mark.parametrize("case", sorted(_BOUND_BY_SCOPING))
def test_unresolved_free_names_accepts_names_bound_by_scoping(case: str) -> None:
    code = _BOUND_BY_SCOPING[case]
    tree = ast.parse(code)
    assert PatternValidators.check_no_unresolved_free_names(tree, "test.py") == []


@pytest.mark.parametrize("name", ["__file__", "__builtins__", "__cached__"])
def test_unresolved_free_names_accepts_interpreter_module_names(name: str) -> None:
    """Module attributes the interpreter sets without an assignment and that
    are not builtins (``__name__`` & co. already are)."""
    code = f"""
def test_x():
    assert {name} is not None or True
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_unresolved_free_names(tree, "test.py", code) == []


def test_unresolved_free_names_flags_name_only_used_in_comprehension() -> None:
    code = """
def test_x():
    assert [undefined_y for _ in range(3)]
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py", code)
    assert len(v) == 1
    assert "'undefined_y' at line 3" in v[0].message


def test_unresolved_free_names_flags_free_name_inside_decorator_lambda() -> None:
    code = """
import pytest

@pytest.mark.parametrize("f", [lambda b: missing_v(b)])
def test_x(f):
    assert f
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py", code)
    assert len(v) == 1
    assert "'missing_v' at line 4" in v[0].message


def test_unresolved_free_names_reports_line_of_the_unbound_use() -> None:
    """A name bound in one scope but free in another is flagged at the free use."""
    code = """
def test_a():
    finding = 1
    assert finding

def test_b():
    assert finding
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py", code)
    assert len(v) == 1
    assert "'finding' at line 7" in v[0].message


def test_unresolved_free_names_fails_closed_when_source_does_not_compile() -> None:
    """Parses but does not compile: no compiler view, so the gate refuses
    rather than relying on a later gate (governor ruling 2026-10-03)."""
    code = """
def test_x():
    nonlocal missing
    assert missing
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py", code)
    assert len(v) == 1
    assert v[0].rule_name == "code.tests.no_unresolved_free_names"
    assert "does not compile" in v[0].message


def test_unresolved_free_names_fails_closed_on_unmatched_scope() -> None:
    """A scope the walker cannot pair with its symbol table (here a PEP 695
    ``type`` alias) is refused, not silently skipped."""
    code = """
type Alias = list[int]

def test_x():
    assert Alias
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py", code)
    assert len(v) == 1
    assert v[0].rule_name == "code.tests.no_unresolved_free_names"
    assert "could not be matched" in v[0].message


def test_unresolved_free_names_accepts_generic_function() -> None:
    code = """
def ident[T](value: T) -> T:
    return value

def test_x():
    assert ident(1) == 1
"""
    tree = ast.parse(code)
    assert PatternValidators.check_no_unresolved_free_names(tree, "test.py", code) == []


def test_unresolved_free_names_flags_free_name_in_generic_function() -> None:
    code = """
def ident[T](value: T) -> T:
    return missing_w

def test_x():
    assert ident(1)
"""
    tree = ast.parse(code)
    v = PatternValidators.check_no_unresolved_free_names(tree, "test.py", code)
    assert len(v) == 1
    assert "'missing_w' at line 3" in v[0].message


def test_validate_test_file_pattern_accepts_comprehension_target() -> None:
    """The public entry point carries the scoping fix, not just the helper."""
    code = """
def test_x():
    assert all(rule_id for rule_id in ["a"])
"""
    v = PatternValidators.validate_test_file_pattern(code, "test.py")
    assert [r for r in v if r.rule_name == "code.tests.no_unresolved_free_names"] == []


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
