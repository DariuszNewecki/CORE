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
