"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/ast_utility.py
- Symbol: parse_metadata_comment
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:11:43
"""

import ast

from shared.ast_utility import parse_metadata_comment


# Detected return type: dict[str, str]


def test_parse_metadata_comment_no_lineno():
    """Test node without lineno attribute returns empty dict."""
    node = ast.parse("x = 1").body[0]
    source_lines = ["# CAPABILITY: test.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {}


def test_parse_metadata_comment_lineno_one():
    """Test node with lineno == 1 returns empty dict."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 1
    source_lines = ["x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {}


def test_parse_metadata_comment_no_comment_line():
    """Test line above node is not a comment."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["y = 2", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {}


def test_parse_metadata_comment_comment_without_capability():
    """Test comment line without CAPABILITY keyword."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# Some other comment", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {}


def test_parse_metadata_comment_capability_lowercase():
    """Test case-insensitive matching of 'CAPABILITY:'."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# capability: domain.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key"}


def test_parse_metadata_comment_capability_mixed_case():
    """Test case-insensitive matching with mixed case."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# CaPaBiLiTy: domain.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key"}


def test_parse_metadata_comment_valid_capability():
    """Test valid CAPABILITY comment returns correct dict."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# CAPABILITY: domain.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key"}


def test_parse_metadata_comment_value_with_colon():
    """Test capability value containing a colon."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# CAPABILITY: domain.key:subkey", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key:subkey"}


def test_parse_metadata_comment_value_with_leading_trailing_spaces():
    """Test capability value stripping."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# CAPABILITY:   domain.key   ", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key"}


def test_parse_metadata_comment_comment_with_leading_spaces():
    """Test comment line with leading spaces."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["   # CAPABILITY: domain.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key"}


def test_parse_metadata_comment_malformed_no_colon():
    """Test comment with CAPABILITY but no colon raises ValueError and returns empty dict."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# CAPABILITY domain.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {}


def test_parse_metadata_comment_capability_not_at_start_of_comment():
    """Test CAPABILITY appears after comment start."""
    node = ast.parse("x = 1").body[0]
    node.lineno = 2
    source_lines = ["# Some text CAPABILITY: domain.key", "x = 1"]
    result = parse_metadata_comment(node, source_lines)
    assert result == {"capability": "domain.key"}
