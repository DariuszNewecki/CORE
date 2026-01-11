"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/ast_gate/checks/logging_checks.py
- Symbol: LoggingChecks
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:32:37
"""

import ast

from mind.logic.engines.ast_gate.checks.logging_checks import LoggingChecks


# Detected return type: list[str]


def test_check_no_print_statements_no_findings():
    """Test that a tree without print statements returns an empty list."""
    source = """
def some_function():
    x = 1 + 2
    logger.info("This is fine")
"""
    tree = ast.parse(source)
    result = LoggingChecks.check_no_print_statements(tree)
    assert result == []


def test_check_no_print_statements_single_print():
    """Test detection of a single print() call."""
    source = """
def some_function():
    x = 1
    print("Hello")
"""
    tree = ast.parse(source)
    result = LoggingChecks.check_no_print_statements(tree)
    expected_line = 4  # Line number of 'print' in the parsed source
    assert result == [
        f"Line {expected_line}: Replace print() with logger.info() or logger.debug()"
    ]


def test_check_no_print_statements_multiple_prints():
    """Test detection of multiple print() calls."""
    source = """
print("Start")
def func():
    y = 2
    print("Inside")
    print("Again")
"""
    tree = ast.parse(source)
    result = LoggingChecks.check_no_print_statements(tree)
    # Order should follow ast.walk order
    assert len(result) == 3
    assert all(
        "Replace print() with logger.info() or logger.debug()" in msg for msg in result
    )


def test_check_no_print_statements_print_in_expression():
    """Test that print() is detected even when part of a larger expression."""
    source = """
x = print("value") or True
"""
    tree = ast.parse(source)
    result = LoggingChecks.check_no_print_statements(tree)
    expected_line = 2
    assert result == [
        f"Line {expected_line}: Replace print() with logger.info() or logger.debug()"
    ]


def test_check_no_print_statements_not_a_call():
    """Test that a variable named 'print' is not flagged."""
    source = """
print = "not a function"
"""
    tree = ast.parse(source)
    result = LoggingChecks.check_no_print_statements(tree)
    assert result == []
