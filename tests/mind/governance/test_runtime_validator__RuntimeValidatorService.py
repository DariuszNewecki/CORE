"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/runtime_validator.py
- Symbol: RuntimeValidatorService
- Status: 6 tests passed, some failed
- Passing tests: test_init_with_path_object, test_init_with_string_path, test_init_resolves_path, test_run_tests_in_canary_success_mock, test_run_tests_in_canary_with_relative_path, test_run_tests_in_canary_exception_handling
- Generated: 2026-01-11 01:46:31
"""

from pathlib import Path

from body.governance.runtime_validator import RuntimeValidatorService


class TestRuntimeValidatorService:

    def test_init_with_path_object(self):
        """Test initialization with Path object."""
        test_path = Path("/some/repo")
        service = RuntimeValidatorService(test_path)
        assert service.repo_root == Path("/some/repo").resolve()
        assert service.test_timeout == 60

    def test_init_with_string_path(self):
        """Test initialization with string path."""
        service = RuntimeValidatorService("/some/repo")
        assert service.repo_root == Path("/some/repo").resolve()

    def test_init_resolves_path(self):
        """Test that repo_root is resolved to absolute path."""
        service = RuntimeValidatorService(".")
        assert service.repo_root.is_absolute()
