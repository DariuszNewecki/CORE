from __future__ import annotations

from unittest.mock import patch

from mind.logic.engines.ast_gate.checks.metadata_checks import verify_metadata_only_diff


# ID: 450f2d38-b936-458f-a6e4-dcfb1a25ea52
def test_verify_metadata_only_diff():
    original = "def f():\n    return 1\n"
    modified = "def f():\n    # add a comment\n    return 1\n"

    # normalize_ast is a local/consuming-module dependency; patch via its defining path.
    with (
        patch(
            "mind.logic.engines.ast_gate.checks.metadata_checks.normalize_ast",
            side_effect=lambda code: "NORM",
        ) as mock_norm,
        patch(
            "mind.logic.engines.ast_gate.checks.metadata_checks._detect_operations",
            return_value={"comment"},
        ) as mock_detect,
    ):
        result = verify_metadata_only_diff(
            original,
            modified,
            params={"max_comment_length": 50, "allowed_operations": ["comment"]},
        )

    assert result == []
    assert mock_norm.call_count == 2
    mock_detect.assert_called_once_with(original, modified)


from mind.logic.engines.ast_gate.checks.metadata_checks import normalize_ast


# ID: ff19d4bf-6c6d-43c3-985a-ea68ff6707f7
def test_normalize_ast():
    code = '''"""Module docstring."""


# ID: d98c6d64-9d9a-468c-8c4d-5d7c9b8d1312
def foo():
    """Function docstring."""
    return 1
'''
    result = normalize_ast(code)
    assert isinstance(result, str)
    assert result  # non-empty canonical AST string
    # Docstrings and line/col attributes should be stripped, so two
    # semantically-equivalent snippets normalize identically.
    code_without_docstrings = """def foo():
    return 1
"""
    assert normalize_ast(code_without_docstrings) == result
