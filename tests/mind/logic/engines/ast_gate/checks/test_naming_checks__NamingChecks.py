"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/naming_checks.py
- Symbol: NamingChecks
- Status: 22 tests passed, some failed
- Passing tests: test_no_async_functions, test_private_async_function, test_public_async_function_violation, test_magic_async_method, test_mixed_async_functions, test_non_test_file, test_properly_named_test_file, test_test_file_without_prefix, test_test_file_case_insensitive, test_test_generation_exception, test_test_in_middle_of_filename, test_file_within_limit, test_file_exceeds_limit, test_default_limit, test_empty_file, test_custom_limit, test_function_within_limit, test_function_exceeds_limit, test_magic_method_ignored, test_async_function_check, test_multiple_violations, test_default_limit
- Generated: 2026-01-11 02:29:07
"""

import ast

from mind.logic.engines.ast_gate.checks.naming_checks import NamingChecks


class TestCheckCliAsyncHelpersPrivate:

    def test_no_async_functions(self):
        """Test when tree has no async functions"""
        code = "\ndef regular_function():\n    pass\n    \nclass MyClass:\n    def method(self):\n        pass\n"
        tree = ast.parse(code)
        result = NamingChecks.check_cli_async_helpers_private(tree)
        assert result == []

    def test_private_async_function(self):
        """Test async function starting with underscore should be ignored"""
        code = "\nasync def _private_helper():\n    pass\n"
        tree = ast.parse(code)
        result = NamingChecks.check_cli_async_helpers_private(tree)
        assert result == []

    def test_public_async_function_violation(self):
        """Test public async function should trigger finding"""
        code = "\nasync def public_helper():\n    pass\n"
        tree = ast.parse(code)
        result = NamingChecks.check_cli_async_helpers_private(tree)
        assert len(result) == 1
        assert "Async helper 'public_helper' must be private" in result[0]
        assert "Line 2" in result[0]

    def test_magic_async_method(self):
        """Test async magic methods should be ignored"""
        code = "\nclass MyClass:\n    async def __call__(self):\n        pass\n"
        tree = ast.parse(code)
        result = NamingChecks.check_cli_async_helpers_private(tree)
        assert result == []

    def test_mixed_async_functions(self):
        """Test mix of public, private, and magic async functions"""
        code = "\nasync def public_one():\n    pass\n    \nasync def _private_one():\n    pass\n    \nasync def __magic__():\n    pass\n    \nasync def another_public():\n    pass\n"
        tree = ast.parse(code)
        result = NamingChecks.check_cli_async_helpers_private(tree)
        assert len(result) == 2
        findings_text = " ".join(result)
        assert "public_one" in findings_text
        assert "another_public" in findings_text
        assert "_private_one" not in findings_text
        assert "__magic__" not in findings_text


class TestCheckTestFileNaming:

    def test_non_test_file(self):
        """Test file without 'test' in name should pass"""
        result = NamingChecks.check_test_file_naming("/path/to/module.py")
        assert result == []

    def test_properly_named_test_file(self):
        """Test file starting with 'test_' should pass"""
        result = NamingChecks.check_test_file_naming("/path/to/test_module.py")
        assert result == []

    def test_test_file_without_prefix(self):
        """Test file containing 'test' but not starting with 'test_' should fail"""
        result = NamingChecks.check_test_file_naming("/path/to/unittest_module.py")
        assert len(result) == 1
        assert "unittest_module.py" in result[0]
        assert "must be prefixed with 'test_'" in result[0]

    def test_test_file_case_insensitive(self):
        """Test case-insensitive detection of 'test'"""
        result = NamingChecks.check_test_file_naming("/path/to/TEST_module.py")
        assert len(result) == 1
        assert "TEST_module.py" in result[0]

    def test_test_generation_exception(self):
        """Test 'test_generation' in path should be ignored"""
        result = NamingChecks.check_test_file_naming(
            "/path/to/test_generation/module.py"
        )
        assert result == []
        result = NamingChecks.check_test_file_naming(
            "/test_generation/unittest_module.py"
        )
        assert result == []

    def test_test_in_middle_of_filename(self):
        """Test 'test' in middle of filename without prefix"""
        result = NamingChecks.check_test_file_naming("/path/to/mytestfile.py")
        assert len(result) == 1
        assert "mytestfile.py" in result[0]


class TestCheckMaxFileLines:

    def test_file_within_limit(self):
        """Test file with line count within limit"""
        code = "x = 1\ny = 2\nz = 3\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_file_lines(tree, "/path/to/file.py", limit=10)
        assert result == []

    def test_file_exceeds_limit(self):
        """Test file exceeding line limit"""
        code = "\n".join([f"x{i} = {i}" for i in range(50)])
        tree = ast.parse(code)
        result = NamingChecks.check_max_file_lines(tree, "/path/to/file.py", limit=10)
        assert len(result) == 1
        assert "exceeds limit of 10" in result[0]
        assert "50" in result[0] or "49" in result[0]

    def test_default_limit(self):
        """Test with default limit of 400"""
        code = "\n".join([f"x{i} = {i}" for i in range(500)])
        tree = ast.parse(code)
        result = NamingChecks.check_max_file_lines(tree, "/path/to/file.py")
        assert len(result) == 1
        assert "exceeds limit of 400" in result[0]

    def test_empty_file(self):
        """Test empty file"""
        tree = ast.parse("")
        result = NamingChecks.check_max_file_lines(tree, "/path/to/file.py", limit=10)
        assert result == []

    def test_custom_limit(self):
        """Test with custom limit parameter"""
        code = "x = 1\ny = 2\nz = 3\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_file_lines(tree, "/path/to/file.py", limit=2)
        assert len(result) == 1
        assert "exceeds limit of 2" in result[0]


class TestCheckMaxFunctionLength:

    def test_function_within_limit(self):
        """Test function within line limit"""
        code = "\ndef short_function():\n    x = 1\n    y = 2\n    return x + y\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_function_length(tree, limit=10)
        assert result == []

    def test_function_exceeds_limit(self):
        """Test function exceeding line limit"""
        code = "\ndef long_function():\n    x = 1\n    y = 2\n    z = 3\n    a = 4\n    b = 5\n    c = 6\n    d = 7\n    e = 8\n    f = 9\n    g = 10\n    return sum([x, y, z, a, b, c, d, e, f, g])\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_function_length(tree, limit=5)
        assert len(result) == 1
        assert "Function 'long_function' has " in result[0]
        assert "exceeds limit of 5" in result[0]

    def test_magic_method_ignored(self):
        """Test magic methods are ignored"""
        code = "\ndef __init__(self):\n    # Many lines\n    x = 1\n    y = 2\n    z = 3\n    a = 4\n    b = 5\n    c = 6\n    d = 7\n    e = 8\n    f = 9\n    g = 10\n    h = 11\n    i = 12\n    j = 13\n    k = 14\n    l = 15\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_function_length(tree, limit=5)
        assert result == []

    def test_async_function_check(self):
        """Test async functions are also checked"""
        code = "\nasync def long_async_function():\n    x = 1\n    y = 2\n    z = 3\n    a = 4\n    b = 5\n    c = 6\n    d = 7\n    e = 8\n    f = 9\n    g = 10\n    await some_operation()\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_function_length(tree, limit=5)
        assert len(result) == 1
        assert "long_async_function" in result[0]

    def test_multiple_violations(self):
        """Test multiple functions exceeding limit"""
        code = "\ndef first_long():\n    x = 1\n    y = 2\n    z = 3\n    a = 4\n    b = 5\n    \ndef second_long():\n    a = 1\n    b = 2\n    c = 3\n    d = 4\n    e = 5\n    f = 6\n    \ndef short():\n    pass\n"
        tree = ast.parse(code)
        result = NamingChecks.check_max_function_length(tree, limit=3)
        assert len(result) == 2
        findings_text = " ".join(result)
        assert "first_long" in findings_text
        assert "second_long" in findings_text
        assert "short" not in findings_text

    def test_default_limit(self):
        """Test with default limit of 50"""
        code = "\ndef very_long_function():\n    # 60 lines of code\n" + "\n".join(
            [f"    x{i} = {i}" for i in range(60)]
        )
        tree = ast.parse(code)
        result = NamingChecks.check_max_function_length(tree)
        assert len(result) == 1
        assert "exceeds limit of 50" in result[0]
