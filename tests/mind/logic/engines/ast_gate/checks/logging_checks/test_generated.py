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
