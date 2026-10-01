from __future__ import annotations

from mind.logic.engines.ast_gate.checks.naming_checks import NamingChecks


# ID: dd86076b-0d56-4673-9684-788adda70491
def test_NamingChecks_check_test_file_naming() -> None:
    checks = NamingChecks()

    # Happy path: properly prefixed test file yields no findings
    assert checks.check_test_file_naming("tests/test_my_module.py") == []

    # Misnamed test file that contains "test" without the prefix
    findings = checks.check_test_file_naming("tests/my_test_module.py")
    assert findings == ["Test file 'my_test_module.py' must be prefixed with 'test_'"]

    # Files without "test" are ignored
    assert checks.check_test_file_naming("src/mind/module.py") == []

    # test_generation path is exempted
    assert checks.check_test_file_naming("tests/test_generation/my_test.py") == []


import ast
from unittest.mock import patch

from mind.logic.engines.ast_gate.checks.naming_checks import (
    ASTHelpers,
)


# ID: 00b28107-9dd3-4868-ac57-db6c6d0459aa
def test_NamingChecks_check_cli_async_helpers_private() -> None:
    source = (
        "async def _private_helper():\n"
        "    pass\n"
        "async def __dunder_helper__():\n"
        "    pass\n"
        "async def public_helper():\n"
        "    pass\n"
    )
    tree = ast.parse(source)

    with patch.object(ASTHelpers, "lineno", return_value=5) as mock_lineno:
        result = NamingChecks.check_cli_async_helpers_private(tree)

    assert result == [
        "Line 5: Async helper 'public_helper' must be private (start with _)"
    ]
    mock_lineno.assert_called_once()
