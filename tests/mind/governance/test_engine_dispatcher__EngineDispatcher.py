"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/engine_dispatcher.py
- Symbol: EngineDispatcher
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:12:54
"""

from pathlib import Path
from unittest.mock import Mock, patch

from mind.governance.engine_dispatcher import EngineDispatcher


# Detected return type: EngineDispatcher.invoke_engine returns list[ViolationReport]


class TestEngineDispatcher:
    """Unit tests for EngineDispatcher.invoke_engine"""

    def test_invoke_engine_skips_nonexistent_file(self):
        """Test that non-existent files are skipped without engine invocation"""
        # Arrange
        rule = Mock()
        rule.engine = "test_engine"
        rule.name = "test_rule"
        rule.params = {}
        rule.description = "Test description"
        rule.severity = "warning"
        rule.source_policy = "test_policy"

        non_existent_path = Path("/non/existent/file.txt")
        path_str = "relative/path.txt"

        # Act
        result = EngineDispatcher.invoke_engine(rule, non_existent_path, path_str)

        # Assert
        assert result == []
        # No engine should be invoked for non-existent files

    def test_invoke_engine_skips_directory(self):
        """Test that directories are skipped without engine invocation"""
        # Arrange
        rule = Mock()
        rule.engine = "test_engine"
        rule.name = "test_rule"
        rule.params = {}
        rule.description = "Test description"
        rule.severity = "warning"
        rule.source_policy = "test_policy"

        # Create a mock directory path
        dir_path = Mock(spec=Path)
        dir_path.exists.return_value = True
        dir_path.is_file.return_value = False
        path_str = "some/directory/"

        # Act
        result = EngineDispatcher.invoke_engine(rule, dir_path, path_str)

        # Assert
        assert result == []
        # No engine should be invoked for directories

    def test_invoke_engine_successful_no_violations(self):
        """Test successful engine invocation with no violations"""
        # Arrange
        rule = Mock()
        rule.engine = "test_engine"
        rule.name = "test_rule"
        rule.params = {"param1": "value1"}
        rule.description = "Test description"
        rule.severity = "warning"
        rule.source_policy = "test_policy"

        file_path = Mock(spec=Path)
        file_path.exists.return_value = True
        file_path.is_file.return_value = True
        path_str = "relative/file.txt"

        # Mock engine result with no violations
        mock_result = Mock()
        mock_result.ok = True
        mock_result.violations = []

        mock_engine = Mock()
        mock_engine.verify.return_value = mock_result

        with patch(
            "mind.governance.engine_dispatcher.EngineRegistry.get",
            return_value=mock_engine,
        ):
            # Act
            result = EngineDispatcher.invoke_engine(rule, file_path, path_str)

            # Assert
            assert result == []
            mock_engine.verify.assert_called_once_with(file_path, {"param1": "value1"})

    def test_invoke_engine_with_violations(self):
        """Test engine invocation that returns violations"""
        # Arrange
        rule = Mock()
        rule.engine = "test_engine"
        rule.name = "test_rule"
        rule.params = {}
        rule.description = "Check for bad patterns"
        rule.severity = "error"
        rule.source_policy = "security_policy"

        file_path = Mock(spec=Path)
        file_path.exists.return_value = True
        file_path.is_file.return_value = True
        path_str = "src/main.py"

        # Mock engine result with violations
        mock_result = Mock()
        mock_result.ok = False
        mock_result.violations = ["Hardcoded password detected", "Insecure API call"]

        mock_engine = Mock()
        mock_engine.verify.return_value = mock_result

        with patch(
            "mind.governance.engine_dispatcher.EngineRegistry.get",
            return_value=mock_engine,
        ):
            # Act
            result = EngineDispatcher.invoke_engine(rule, file_path, path_str)

            # Assert
            assert len(result) == 2

            # Check first violation
            assert result[0].rule_name == "test_rule"
            assert result[0].path == "src/main.py"
            assert (
                result[0].message
                == "Check for bad patterns: Hardcoded password detected"
            )
            assert result[0].severity == "error"
            assert result[0].source_policy == "security_policy"

            # Check second violation
            assert result[1].rule_name == "test_rule"
            assert result[1].path == "src/main.py"
            assert result[1].message == "Check for bad patterns: Insecure API call"
            assert result[1].severity == "error"
            assert result[1].source_policy == "security_policy"

    def test_invoke_engine_handles_exception(self):
        """Test that engine exceptions are caught and reported as violations"""
        # Arrange
        rule = Mock()
        rule.engine = "failing_engine"
        rule.name = "test_rule"
        rule.params = {}
        rule.description = "Test description"
        rule.severity = "warning"
        rule.source_policy = "test_policy"

        file_path = Mock(spec=Path)
        file_path.exists.return_value = True
        file_path.is_file.return_value = True
        path_str = "test/file.py"

        # Mock engine that raises an exception
        mock_engine = Mock()
        mock_engine.verify.side_effect = ValueError("Engine configuration error")

        with patch(
            "mind.governance.engine_dispatcher.EngineRegistry.get",
            return_value=mock_engine,
        ):
            # Act
            result = EngineDispatcher.invoke_engine(rule, file_path, path_str)

            # Assert
            assert len(result) == 1
            violation = result[0]
            assert violation.rule_name == "test_rule"
            assert violation.path == "test/file.py"
            assert (
                violation.message
                == "Engine failure (failing_engine): Engine configuration error"
            )
            assert violation.severity == "error"
            assert violation.source_policy == "test_policy"

    def test_invoke_engine_with_none_params(self):
        """Test engine invocation when rule.params is None"""
        # Arrange
        rule = Mock()
        rule.engine = "test_engine"
        rule.name = "test_rule"
        rule.params = None  # Explicitly None
        rule.description = "Test description"
        rule.severity = "info"
        rule.source_policy = "test_policy"

        file_path = Mock(spec=Path)
        file_path.exists.return_value = True
        file_path.is_file.return_value = True
        path_str = "file.txt"

        mock_result = Mock()
        mock_result.ok = True
        mock_result.violations = []

        mock_engine = Mock()
        mock_engine.verify.return_value = mock_result

        with patch(
            "mind.governance.engine_dispatcher.EngineRegistry.get",
            return_value=mock_engine,
        ):
            # Act
            result = EngineDispatcher.invoke_engine(rule, file_path, path_str)

            # Assert
            assert result == []
            # Should pass empty dict when params is None
            mock_engine.verify.assert_called_once_with(file_path, {})

    def test_invoke_engine_empty_violation_messages(self):
        """Test engine with empty violation messages list"""
        # Arrange
        rule = Mock()
        rule.engine = "test_engine"
        rule.name = "test_rule"
        rule.params = {}
        rule.description = "Test description"
        rule.severity = "warning"
        rule.source_policy = "test_policy"

        file_path = Mock(spec=Path)
        file_path.exists.return_value = True
        file_path.is_file.return_value = True
        path_str = "file.txt"

        # Mock engine result with ok=False but empty violations
        mock_result = Mock()
        mock_result.ok = False
        mock_result.violations = []  # Empty list

        mock_engine = Mock()
        mock_engine.verify.return_value = mock_result

        with patch(
            "mind.governance.engine_dispatcher.EngineRegistry.get",
            return_value=mock_engine,
        ):
            # Act
            result = EngineDispatcher.invoke_engine(rule, file_path, path_str)

            # Assert
            assert (
                result == []
            )  # Should return empty list when violations list is empty
