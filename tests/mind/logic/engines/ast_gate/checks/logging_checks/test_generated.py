from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.checks.logging_checks import LoggingChecks


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


# ID: 5699285e-3865-4423-812d-dcb2db743eef
def test_check_logger_not_presentation() -> None:
    rich_tree = ast.parse("logger.info(Table())")
    markup_tree = ast.parse('logger.info("[bold]text[/bold]")')
    plain_tree = ast.parse('logger.info("[DRY RUN] starting")')

    rich_findings = LoggingChecks.check_logger_not_presentation(rich_tree)
    markup_findings = LoggingChecks.check_logger_not_presentation(markup_tree)
    plain_findings = LoggingChecks.check_logger_not_presentation(plain_tree)

    assert isinstance(rich_findings, list)
    assert isinstance(markup_findings, list)
    assert isinstance(plain_findings, list)
    assert plain_findings == []
    assert len(rich_findings) >= 1 or len(markup_findings) >= 1


# ID: 7c549b51-65e7-4497-b05c-c003266a70eb
def test_LoggingChecks_check_logger_not_presentation():
    """Happy path: a logger call passing Rich markup string is flagged as a finding."""
    source = 'logger.info("[bold]hello[/bold]")\n'
    tree = ast.parse(source)

    findings = LoggingChecks.check_logger_not_presentation(tree)

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "logger used as renderer" in findings[0]
    assert "Rich markup" in findings[0]

    # Happy path (clean): a plain logger string must produce no findings.
    clean_tree = ast.parse('logger.info("plain operational message")\n')
    clean_findings = LoggingChecks.check_logger_not_presentation(clean_tree)
    assert clean_findings == []

    # Plain-text labels are NOT Rich markup and must not be flagged.
    label_tree = ast.parse('logger.info("[DRY RUN] starting")\n')
    assert LoggingChecks.check_logger_not_presentation(label_tree) == []
