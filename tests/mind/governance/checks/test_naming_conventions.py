# tests/mind/governance/checks/test_naming_conventions.py
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mind.governance.checks.naming_conventions import NamingConventionsCheck
from shared.models import AuditSeverity


# A realistic, minimal policy for testing purposes.
# We will modify this in specific tests to check edge cases.
TEST_POLICY = {
    "code_standards": {
        "naming_conventions": {
            "intent": [
                {
                    "id": "intent.policy_file_naming",
                    "description": "Policy files must use snake_case and end with '.yaml'.",
                    "enforcement": "error",
                    "scope": ".intent/charter/policies/*.yaml",
                    "pattern": "^[a-z0-9_]+\\.yaml$",
                }
            ],
            "code": [
                {
                    "id": "code.python_module_naming",
                    "description": "Python source files must use snake_case.",
                    "enforcement": "error",
                    "scope": "src/**/*.py",
                    "pattern": "^[a-z0-9_]+\\.py$",
                    "exclusions": ["__init__.py"],
                },
                {
                    "id": "code.python_test_module_naming",
                    "description": "Python test files must be prefixed with 'test_'.",
                    "enforcement": "error",
                    "scope": "tests/**/*.py",
                    "pattern": "^test_[a-z0-9_]+\\.py$",
                    "exclusions": ["__init__.py", "conftest.py"],
                },
            ],
        }
    }
}


@pytest.fixture
def mock_context(tmp_path: Path) -> MagicMock:
    """Creates a mock AuditorContext with a temporary repo_root and a default policy."""
    context = MagicMock()
    context.repo_root = tmp_path
    context.policies = TEST_POLICY
    return context


class TestNamingConventionsCheck:
    """Test suite for the NamingConventionsCheck."""

    def test_finds_violation_in_python_module_name(self, mock_context):
        """Verify that a Python file with an invalid name is flagged."""
        # Arrange
        (mock_context.repo_root / "src" / "features").mkdir(parents=True)
        bad_file = mock_context.repo_root / "src" / "features" / "MyBadModule.py"
        bad_file.touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "code.python_module_naming"
        assert finding.severity == AuditSeverity.ERROR
        assert "MyBadModule.py" in finding.message
        assert str(finding.file_path) == "src/features/MyBadModule.py"

    def test_no_violation_for_correct_python_module_name(self, mock_context):
        """Verify that a correctly named Python file passes."""
        # Arrange
        (mock_context.repo_root / "src" / "features").mkdir(parents=True)
        good_file = mock_context.repo_root / "src" / "features" / "good_module.py"
        good_file.touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 0

    def test_finds_violation_in_test_module_name(self, mock_context):
        """Verify that a test file not prefixed with 'test_' is flagged."""
        # Arrange
        (mock_context.repo_root / "tests" / "features").mkdir(parents=True)
        bad_file = mock_context.repo_root / "tests" / "features" / "my_feature_test.py"
        bad_file.touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 1
        assert findings[0].check_id == "code.python_test_module_naming"
        assert "my_feature_test.py" in findings[0].message

    def test_no_violation_for_correct_test_module_name(self, mock_context):
        """Verify that a correctly named test file passes."""
        # Arrange
        (mock_context.repo_root / "tests" / "features").mkdir(parents=True)
        good_file = mock_context.repo_root / "tests" / "features" / "test_my_feature.py"
        good_file.touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 0

    def test_exclusion_for_init_py_is_respected(self, mock_context):
        """Verify that '__init__.py' files are correctly excluded."""
        # Arrange
        (mock_context.repo_root / "src").mkdir()
        (mock_context.repo_root / "tests").mkdir()
        (mock_context.repo_root / "src" / "__init__.py").touch()
        (mock_context.repo_root / "tests" / "__init__.py").touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 0, "Dunder init files should be excluded by the policy"

    def test_exclusion_for_conftest_py_is_respected(self, mock_context):
        """Verify that 'conftest.py' is correctly excluded."""
        # Arrange
        (mock_context.repo_root / "tests").mkdir()
        (mock_context.repo_root / "tests" / "conftest.py").touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 0, "conftest.py should be excluded by the policy"

    def test_finds_violation_in_intent_policy_name(self, mock_context):
        """Verify a violation is found for a badly named policy file."""
        # Arrange
        policy_dir = mock_context.repo_root / ".intent" / "charter" / "policies"
        policy_dir.mkdir(parents=True)
        bad_file = policy_dir / "BadPolicy.yaml"
        bad_file.touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 1
        assert findings[0].check_id == "intent.policy_file_naming"
        assert "BadPolicy.yaml" in findings[0].message

    def test_handles_empty_policy_gracefully(self, mock_context):
        """Verify the check returns no findings if the policy section is missing."""
        # Arrange
        mock_context.policies = {"code_standards": {}}  # No naming_conventions key

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 0

    def test_skips_malformed_rules_without_scope(self, mock_context):
        """Verify rules missing a 'scope' or 'pattern' are skipped without error."""
        # Arrange
        malformed_policy = {
            "code_standards": {
                "naming_conventions": {
                    "code": [
                        {"id": "malformed.rule", "pattern": ".*"}  # Missing 'scope'
                    ]
                }
            }
        }
        mock_context.policies = malformed_policy
        (mock_context.repo_root / "src").mkdir()
        (mock_context.repo_root / "src" / "some_file.py").touch()

        # Act
        check = NamingConventionsCheck(mock_context)
        findings = check.execute()

        # Assert
        assert len(findings) == 0, "Malformed rules should be skipped"

    def test_skips_rules_with_invalid_regex_pattern(self, mock_context):
        """Verify that an invalid regex in the policy doesn't crash the auditor."""
        # Arrange
        bad_regex_policy = {
            "code_standards": {
                "naming_conventions": {
                    "code": [
                        {
                            "id": "bad.regex",
                            "scope": "src/*.py",
                            "pattern": "[a-z",  # Invalid regex
                        }
                    ]
                }
            }
        }
        mock_context.policies = bad_regex_policy
        (mock_context.repo_root / "src").mkdir()
        (mock_context.repo_root / "src" / "some_file.py").touch()

        # Act & Assert (should not raise an exception)
        try:
            check = NamingConventionsCheck(mock_context)
            findings = check.execute()
            assert len(findings) == 0, "Rules with invalid regex should be skipped"
        except Exception as e:
            pytest.fail(f"Check crashed on invalid regex: {e}")
