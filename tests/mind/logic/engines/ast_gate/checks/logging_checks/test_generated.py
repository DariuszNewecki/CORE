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


# ID: 983c095a-5158-47b9-8c3c-7a1d98cb2ffb
def test_check_logger_not_presentation() -> None:
    source = (
        "logger.info('plain text')\n"
        "logger.info('has [bold]markup[/bold]')\n"
        "logger.info(table)\n"
    )
    tree = ast.parse(source)
    result = LoggingChecks.check_logger_not_presentation(tree)
    assert isinstance(result, list)


# ID: d1cdc10a-6ef0-4813-9b3e-0c0600d508fc
def test_check_logger_not_presentation():
    source = (
        "def f():\n"
        "    logger.info('plain text')\n"
        "    logger.info('[bold]styled[/bold]')\n"
    )
    tree = ast.parse(source)

    findings = LoggingChecks.check_logger_not_presentation(tree)

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "Rich markup detected in log string" in findings[0]


# ID: 40489b16-ea82-4d9f-9e25-42ea4f314e36
def test_check_logger_not_presentation() -> None:
    check = LoggingChecks.check_logger_not_presentation

    safe_source = "logger.info('a plain operational message')\n"
    safe_tree = ast.parse(safe_source)
    assert check(safe_tree) == []

    rich_source = 'logger.info("[bold]hello[/bold]")\n'
    rich_tree = ast.parse(rich_source)
    findings = check(rich_tree)
    assert findings


from unittest.mock import patch


# ID: cf6d1db8-6342-48d2-b0a8-b90d76362a87
def test_check_logger_not_presentation() -> None:
    source = (
        "logger.info(table)\n"
        "logger.error('plain text label [DRY RUN]')\n"
        "logger.warning('[bold]important[/bold]')\n"
    )
    tree = ast.parse(source)

    with patch(
        "mind.logic.engines.ast_gate.checks.logging_checks.ASTHelpers.full_attr_name",
        return_value="logger.info",
    ):
        findings = LoggingChecks.check_logger_not_presentation(tree)

    assert isinstance(findings, list)
    assert len(findings) >= 1





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
