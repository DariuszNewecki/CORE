# tests/body/test_docstring_service.py

"""
Tests for src/body/self_healing/docstring_service.py (issue #455).

Covers two predicate/content gaps relative to the ADR-047 source-of-truth
in PurityChecks.check_docstrings_present:
  - nested functions must be excluded from the remediation candidate set
    (Theme 1, the predicate-drift gap fixed by porting the _parent
    annotation + skip logic)
  - LLM output containing TODO/FIXME/placeholder must be rejected
    (Theme 2, the post-generation content guard)
"""

from __future__ import annotations

import ast

from body.self_healing.docstring_service import (
    _PLACEHOLDER_PATTERN,
    _find_undocumented_public_symbols,
)
from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


def _names(nodes: list[ast.AST]) -> list[str]:
    return [getattr(n, "name", "<?>") for n in nodes]


# -----------------------------------------------------------------------------
# Theme 1 — predicate parity with ADR-047 source-of-truth
# -----------------------------------------------------------------------------


def test_nested_function_excluded_from_remediation_candidates() -> None:
    """Acceptance: `def outer(): def inner(): pass` produces 0 candidates.

    `outer` has a docstring; `inner` has none but is nested. Source-of-truth
    skips nested functions, so the remediation set must also skip it.
    """
    source = '''
def outer():
    """Outer docs."""
    def inner():
        pass
'''
    candidates = _find_undocumented_public_symbols(ast.parse(source))
    assert _names(candidates) == []


def test_nested_function_in_undocumented_outer_still_excluded() -> None:
    """`outer` flagged (no docstring); nested `inner` still excluded."""
    source = """
def outer():
    def inner():
        pass
"""
    candidates = _find_undocumented_public_symbols(ast.parse(source))
    assert _names(candidates) == ["outer"]


def test_method_in_class_is_flagged() -> None:
    """Method (function whose parent is a ClassDef, not a function) must be flagged."""
    source = """
class Widget:
    def method(self):
        pass
"""
    candidates = _find_undocumented_public_symbols(ast.parse(source))
    assert set(_names(candidates)) == {"Widget", "method"}


def test_nested_class_is_still_flagged() -> None:
    """Source-of-truth only parent-skips functions; nested classes are still flagged."""
    source = '''
def container():
    """Container docs."""
    class Inner:
        pass
'''
    candidates = _find_undocumented_public_symbols(ast.parse(source))
    assert _names(candidates) == ["Inner"]


def test_private_symbols_excluded() -> None:
    source = """
def _private():
    pass
def public():
    pass
"""
    candidates = _find_undocumented_public_symbols(ast.parse(source))
    assert _names(candidates) == ["public"]


def test_async_nested_function_excluded() -> None:
    """Async functions get the same parent-skip treatment."""
    source = '''
async def outer():
    """Async outer."""
    async def inner():
        pass
'''
    candidates = _find_undocumented_public_symbols(ast.parse(source))
    assert _names(candidates) == []


def test_predicate_count_matches_source_of_truth_on_mixed_module() -> None:
    """End-to-end parity: the count of remediation candidates equals the
    count of ADR-047 violations on the same source. This is the structural
    guarantee #455 demands ('detection set and remediation candidate set
    match on a representative file with nested functions').
    """
    source = '''
def top_no_doc():
    def nested_no_doc():
        pass

def top_with_doc():
    """Top docs."""
    def nested_no_doc_two():
        pass

class Klass:
    def method_no_doc(self):
        pass
    def _private_method(self):
        pass

class _PrivateKlass:
    pass

async def async_top_no_doc():
    pass
'''
    tree = ast.parse(source)
    remediation = _find_undocumented_public_symbols(tree)
    violations = PurityChecks.check_docstrings_present(ast.parse(source))
    assert len(remediation) == len(violations), (
        f"Predicate drift detected.\n"
        f"  remediation candidates: {sorted(_names(remediation))}\n"
        f"  ADR-047 violations: {violations}"
    )


# -----------------------------------------------------------------------------
# Theme 2 — placeholder-content rejection
# -----------------------------------------------------------------------------


def test_placeholder_pattern_matches_todo() -> None:
    assert _PLACEHOLDER_PATTERN.search('"""TODO: write me."""')


def test_placeholder_pattern_matches_fixme() -> None:
    assert _PLACEHOLDER_PATTERN.search('"""FIXME: explain this."""')


def test_placeholder_pattern_matches_placeholder_word() -> None:
    assert _PLACEHOLDER_PATTERN.search('"""placeholder until reviewer fills in."""')


def test_placeholder_pattern_does_not_match_word_boundary_todo() -> None:
    """`\\bTODO\\b` requires word boundaries — `todomato` must not match."""
    assert not _PLACEHOLDER_PATTERN.search('"""The todomato concept is..."""')


def test_placeholder_pattern_does_not_match_clean_docstring() -> None:
    assert not _PLACEHOLDER_PATTERN.search(
        '"""Return the user\'s greeting in the configured locale."""'
    )
