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


# ID: 587f08a1-2b89-4fad-abfb-4ba6a2656c83
def test_NamingChecks_check_type_annotations() -> None:
    source = (
        "def public_missing():\n"
        "    return 1\n"
        "\n"
        "def public_annotated() -> int:\n"
        "    return 2\n"
        "\n"
        "def _private_missing():\n"
        "    return 3\n"
    )
    tree = ast.parse(source)

    findings = NamingChecks.check_type_annotations(tree)

    assert isinstance(findings, list)
    assert len(findings) == 1
    finding = findings[0]
    assert "public_missing" in finding
    assert "missing a return type annotation" in finding
    assert "public_annotated" not in finding
    assert "_private_missing" not in finding


from unittest.mock import MagicMock


# ID: ed80d2c1-b159-4ad7-ae69-4660d0f6d9b4
def test_NamingChecks() -> None:
    from mind.logic.engines.ast_gate.checks.naming_checks import NamingChecks

    # check_cli_async_helpers_private: public async helper flagged, private not
    tree = ast.parse(
        "async def helper():\n"
        "    pass\n"
        "async def _private_helper():\n"
        "    pass\n"
        "async def __dunder__():\n"
        "    pass\n"
    )
    with patch(
        "mind.logic.engines.ast_gate.checks.naming_checks.ASTHelpers"
    ) as mock_helpers:
        mock_helpers.lineno = MagicMock(return_value=1)
        findings = NamingChecks.check_cli_async_helpers_private(tree)

    assert len(findings) == 1
    assert "helper" in findings[0]
    assert "_private_helper" not in findings[0]

    # check_test_file_naming: non-prefixed test file flagged
    named_findings = NamingChecks.check_test_file_naming("src/pkg/mytest_file.py")
    assert len(named_findings) == 1
    assert "must be prefixed with 'test_'" in named_findings[0]

    # check_max_file_lines: small tree passes under limit
    small_tree = ast.parse("x = 1\n")
    assert NamingChecks.check_max_file_lines(small_tree, "f.py", limit=100) == []

    # check_max_function_length: short function passes under limit
    short_func_tree = ast.parse("def f():\n    return 1\n")
    assert NamingChecks.check_max_function_length(short_func_tree, limit=50) == []

    # check_type_annotations: public function missing return annotation flagged
    untyped_tree = ast.parse("def public_fn():\n    return 1\n")
    with patch(
        "mind.logic.engines.ast_gate.checks.naming_checks.ASTHelpers"
    ) as mock_helpers:
        mock_helpers.lineno = MagicMock(return_value=1)
        anno_findings = NamingChecks.check_type_annotations(untyped_tree)

    assert len(anno_findings) == 1
    assert "public_fn" in anno_findings[0]
