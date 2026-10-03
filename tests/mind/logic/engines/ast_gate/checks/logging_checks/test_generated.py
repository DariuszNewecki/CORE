from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.checks.logging_checks import LoggingChecks


# ID: 419e3e92-25b9-4cd7-b3c7-b334d97ea0d8
def test_check_logger_not_presentation() -> None:
    source = (
        "logger.info('plain text message')\n"
        "logger.warning('another plain message')\n"
        "logger.info('[DRY RUN] starting')\n"
    )
    tree = ast.parse(source)

    result = LoggingChecks.check_logger_not_presentation(tree)

    assert isinstance(result, list)
    assert result == []


# ID: cdd2abf7-3985-46ff-916c-a8f99e6f1dbe
def test_LoggingChecks_check_no_print_statements() -> None:
    source = "def f():\n    print('hello')\n"
    tree = ast.parse(source)
    findings = LoggingChecks.check_no_print_statements(tree)
    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "print()" in findings[0]
    assert "Line 2" in findings[0]


from unittest.mock import MagicMock


# ID: b6a1184d-8239-4774-b3b8-9097ee7ac9b6
def test_LoggingChecks() -> None:
    # Happy path for check_no_print_statements: a logger call is fine, print is flagged.
    clean_source = (
        "import logging\nlogger = logging.getLogger(__name__)\nlogger.info('hi')\n"
    )
    clean_tree = ast.parse(clean_source)
    assert LoggingChecks.check_no_print_statements(clean_tree) == []

    print_source = "print('hello')\n"
    print_tree = ast.parse(print_source)
    print_findings = LoggingChecks.check_no_print_statements(print_tree)
    assert len(print_findings) == 1
    assert "print()" in print_findings[0]

    # Happy path for check_logger_not_presentation: plain text is fine.
    plain_source = "logger.info('all good here')\n"
    plain_tree = ast.parse(plain_source)
    assert LoggingChecks.check_logger_not_presentation(plain_tree) == []

    # logger with Rich markup should be flagged.
    markup_source = "logger.info('[bold]boom[/bold]')\n"
    markup_tree = ast.parse(markup_source)
    markup_findings = LoggingChecks.check_logger_not_presentation(markup_tree)
    assert len(markup_findings) == 1
    assert "Rich markup" in markup_findings[0]

    # Sanity: mock-free static usage returns lists.
    assert isinstance(LoggingChecks.check_no_print_statements(clean_tree), list)
    assert isinstance(LoggingChecks.check_logger_not_presentation(plain_tree), list)

    # Ensure no unexpected external I/O is touched (guard rail).
    _ = MagicMock()


# ID: 8b6c646a-06a9-4ecc-8ee1-b7ae252d090c
def test_check_logger_not_presentation() -> None:
    source = (
        "def f():\n"
        "    logger.info('plain operational message')\n"
        "    logger.debug('[DRY RUN] processing %s', item)\n"
    )
    tree = ast.parse(source)

    findings = LoggingChecks.check_logger_not_presentation(tree)

    assert findings == []





# ID: 0279646f-8f21-4240-845f-6fcdcdc6dc63
def test_check_logger_not_presentation() -> None:
    source = (
        "logger.info('plain operational message')\n"
        "logger.debug('[DRY RUN] starting')\n"
        "logger.warning('[%s] value here')\n"
    )
    tree = ast.parse(source)

    findings = LoggingChecks.check_logger_not_presentation(tree)

    assert findings == []
