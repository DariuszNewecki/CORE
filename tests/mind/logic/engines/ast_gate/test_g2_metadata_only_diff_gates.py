# tests/mind/logic/engines/ast_gate/test_g2_metadata_only_diff_gates.py

"""#842 Unit O: metadata.semantic_preservation and
metadata.operations.comment_length_limit -- the last 2 rows of the G2
fixture-coverage census.

Both rules map to ast_gate's ``metadata_only_diff`` check_type, but
``ASTGateEngine.verify()``'s dispatch for that check_type is a deliberate
audit-time no-op (see the branch at the top of ``verify()``, and the NOTE
in metadata_mutations.yaml): "enforced at action execution time, not audit
time." The real proof mechanism is
``mind.logic.engines.ast_gate.checks.metadata_checks.verify_metadata_only_diff``,
called directly by ``body.atomic.metadata_ops.action_tag_metadata`` at the
point of mutation (confirmed by reading that call site: ``violations =
verify_metadata_only_diff(original_code, code, proof_params)`` where
``proof_params = {"max_comment_length": max_comment_length}``) -- so these
fixtures call the real function directly, not through
``ASTGateEngine.verify()``, which is the confirmed no-op path for this
check_type.

GATE 1 (metadata.semantic_preservation) compares normalized ASTs --
comments are already invisible to ast.parse, so a comment-only edit is a
trivial pass; the meaningful proof is a DOCSTRING content change (which
the function explicitly strips via ``_strip_docstrings`` before
comparing), exercising the actual normalization mechanism rather than
relying on the parser's blindness to comments.

GATE 2 (metadata.operations.comment_length_limit, max_comment_length=120,
matching operational_config.yaml's metadata_max_comment_length) only
inspects NEW comment lines (present in the modified code, absent from the
original) -- both fixtures here keep GATE 1 trivially satisfied (a
comment-only addition) so GATE 2 is what's actually being exercised.
"""

from __future__ import annotations

from mind.logic.engines.ast_gate.checks.metadata_checks import (
    verify_metadata_only_diff,
)


# ---------------------------------------------------------------------------
# metadata.semantic_preservation (GATE 1)
# ---------------------------------------------------------------------------


def test_semantic_preservation_fires_when_executable_ast_changes() -> None:
    original = 'def handler():\n    """Old docstring."""\n    return 1\n'
    modified = 'def handler():\n    """Old docstring."""\n    return 2\n'

    violations = verify_metadata_only_diff(original, modified, {})

    assert violations
    assert any("SEMANTIC PRESERVATION VIOLATED" in v for v in violations)


def test_semantic_preservation_passes_for_docstring_only_change() -> None:
    """Exercises the actual GATE 1 mechanism (_strip_docstrings), not just
    the parser's inherent blindness to comments -- the docstring's string
    content genuinely differs between original and modified, and the
    invariant still holds because docstrings are stripped before the
    normalized-AST comparison."""
    original = 'def handler():\n    """Old docstring."""\n    return 1\n'
    modified = 'def handler():\n    """A completely different docstring."""\n    return 1\n'

    violations = verify_metadata_only_diff(original, modified, {})

    assert violations == []


# ---------------------------------------------------------------------------
# metadata.operations.comment_length_limit (GATE 2)
# ---------------------------------------------------------------------------


def test_comment_length_limit_fires_on_new_comment_over_120_chars() -> None:
    original = "def handler():\n    return 1\n"
    long_comment = "    # " + ("x" * 150)
    modified = f"def handler():\n{long_comment}\n    return 1\n"

    violations = verify_metadata_only_diff(
        original, modified, {"max_comment_length": 120}
    )

    assert violations
    assert any("exceeds 120 chars" in v for v in violations)


def test_comment_length_limit_passes_for_new_comment_within_120_chars() -> None:
    original = "def handler():\n    return 1\n"
    modified = "def handler():\n    # a short new comment\n    return 1\n"

    violations = verify_metadata_only_diff(
        original, modified, {"max_comment_length": 120}
    )

    assert violations == []


def test_comment_length_limit_ignores_preexisting_long_comment() -> None:
    """Only NEW comment lines (absent from the original) are subject to the
    ceiling -- an unchanged pre-existing long comment line is not
    retroactively flagged when a separate, short, genuinely new comment is
    added elsewhere, proving the check's before/after line-set
    discrimination rather than a blanket line-length scan."""
    long_comment = "# " + ("y" * 150)
    original = f"{long_comment}\ndef handler():\n    return 1\n"
    modified = f"{long_comment}\n# a short new comment\ndef handler():\n    return 1\n"

    violations = verify_metadata_only_diff(
        original, modified, {"max_comment_length": 120}
    )

    assert violations == []
