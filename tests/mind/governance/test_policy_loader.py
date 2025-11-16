# tests/mind/governance/test_policy_loader.py
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Import the module under test
from mind.governance import policy_loader


class TestLoadPolicyYaml:
    """Test cases for _load_policy_yaml function."""

    @patch("mind.governance.policy_loader.settings")
    def test_load_valid_yaml_file(self, mock_settings, tmp_path):
        """Test loading a valid YAML policy file."""
        # FIX: Mock settings.REPO_PATH to ensure correct path resolution
        mock_settings.REPO_PATH = tmp_path

        policy_content = {
            "actions": ["action1", "action2"],
            "rules": ["rule1", "rule2"],
        }
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(yaml.dump(policy_content))

        # Test loading the file (passing an absolute path)
        result = policy_loader._load_policy_yaml(policy_file)
        assert result == policy_content

    @patch("mind.governance.policy_loader.settings")
    def test_load_nonexistent_file(self, mock_settings, tmp_path):
        """Test loading a non-existent file raises ValueError."""
        # FIX: Mock settings.REPO_PATH
        mock_settings.REPO_PATH = tmp_path
        non_existent_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(
            ValueError, match=f"Policy file not found: {non_existent_file}"
        ):
            policy_loader._load_policy_yaml(non_existent_file)

    @patch("mind.governance.policy_loader.settings")
    def test_load_invalid_yaml_format(self, mock_settings, tmp_path):
        """Test loading a file with invalid YAML format."""
        # FIX: Mock settings.REPO_PATH
        mock_settings.REPO_PATH = tmp_path
        invalid_yaml_file = tmp_path / "invalid.yaml"
        invalid_yaml_file.write_text("invalid: yaml: content: [")

        with pytest.raises(
            ValueError, match=f"Failed to load policy YAML: {invalid_yaml_file}"
        ):
            policy_loader._load_policy_yaml(invalid_yaml_file)

    @patch("mind.governance.policy_loader.settings")
    def test_load_empty_yaml_file(self, mock_settings, tmp_path):
        """Test loading an empty YAML file returns empty dict."""
        # FIX: Mock settings.REPO_PATH
        mock_settings.REPO_PATH = tmp_path
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        result = policy_loader._load_policy_yaml(empty_file)
        assert result == {}

    @patch("mind.governance.policy_loader.settings")
    def test_load_yaml_with_non_dict_content(self, mock_settings, tmp_path):
        """Test loading YAML that doesn't result in a dictionary."""
        # FIX: Mock settings.REPO_PATH
        mock_settings.REPO_PATH = tmp_path
        list_yaml_file = tmp_path / "list.yaml"
        list_yaml_file.write_text("- item1\n- item2")

        with pytest.raises(
            ValueError, match=f"Policy file must be a dictionary: {list_yaml_file}"
        ):
            policy_loader._load_policy_yaml(list_yaml_file)

    @patch("mind.governance.policy_loader.settings")
    @patch("mind.governance.policy_loader.logger")  # CORRECTED: Was .log
    def test_logging_on_file_not_found(self, mock_logger, mock_settings, tmp_path):
        """Test that appropriate logging occurs when file is not found."""
        # FIX: Mock settings.REPO_PATH
        mock_settings.REPO_PATH = tmp_path
        non_existent_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(ValueError):
            policy_loader._load_policy_yaml(non_existent_file)

        mock_logger.error.assert_called_once_with(
            f"Policy file not found: {non_existent_file}"
        )

    @patch("mind.governance.policy_loader.settings")
    @patch("mind.governance.policy_loader.logger")  # CORRECTED: Was .log
    def test_logging_on_yaml_loading_error(self, mock_logger, mock_settings, tmp_path):
        """Test that appropriate logging occurs when YAML loading fails."""
        # FIX: Mock settings.REPO_PATH
        mock_settings.REPO_PATH = tmp_path
        invalid_yaml_file = tmp_path / "invalid.yaml"
        invalid_yaml_file.write_text("invalid: yaml: [")

        with pytest.raises(ValueError):
            policy_loader._load_policy_yaml(invalid_yaml_file)

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert f"Failed to load policy YAML: {invalid_yaml_file}" in call_args


class TestLoadAvailableActions:
    """Test cases for load_available_actions function."""

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_valid_actions_policy(self, mock_load_policy):
        """Test loading a valid available actions policy."""
        mock_policy = {
            "actions": ["create_file", "modify_file", "delete_file"],
            "version": "1.0",
        }
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_available_actions()

        assert result == mock_policy
        expected_path = policy_loader.GOVERNANCE_DIR / "available_actions_policy.yaml"
        mock_load_policy.assert_called_once_with(expected_path)

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_actions_policy_missing_actions(self, mock_load_policy):
        """Test loading policy with missing actions raises ValueError."""
        mock_policy = {"version": "1.0"}  # Missing 'actions' key
        mock_load_policy.return_value = mock_policy

        with pytest.raises(
            ValueError, match="'actions' must be a non-empty list in the policy."
        ):
            policy_loader.load_available_actions()

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_actions_policy_empty_actions(self, mock_load_policy):
        """Test loading policy with empty actions list raises ValueError."""
        mock_policy = {"actions": [], "version": "1.0"}
        mock_load_policy.return_value = mock_policy

        with pytest.raises(
            ValueError, match="'actions' must be a non-empty list in the policy."
        ):
            policy_loader.load_available_actions()

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_actions_policy_wrong_actions_type(self, mock_load_policy):
        """Test loading policy with wrong type for actions raises ValueError."""
        mock_policy = {"actions": "not_a_list", "version": "1.0"}
        mock_load_policy.return_value = mock_policy

        with pytest.raises(
            ValueError, match="'actions' must be a non-empty list in the policy."
        ):
            policy_loader.load_available_actions()


class TestLoadMicroProposalPolicy:
    """Test cases for load_micro_proposal_policy function."""

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_valid_micro_proposal_policy(self, mock_load_policy):
        """Test loading a valid micro proposal policy."""
        mock_policy = {
            "rules": ["rule1", "rule2", "rule3"],
            "description": "Micro proposal validation rules",
        }
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_micro_proposal_policy()

        assert result == mock_policy
        expected_path = policy_loader.AGENT_DIR / "micro_proposal_policy.yaml"
        mock_load_policy.assert_called_once_with(expected_path)

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_micro_proposal_policy_missing_rules(self, mock_load_policy):
        """Test loading policy with missing rules raises ValueError."""
        mock_policy = {"description": "No rules here"}  # Missing 'rules' key
        mock_load_policy.return_value = mock_policy

        with pytest.raises(
            ValueError, match="'rules' must be a non-empty list in the policy."
        ):
            policy_loader.load_micro_proposal_policy()

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_micro_proposal_policy_empty_rules(self, mock_load_policy):
        """Test loading policy with empty rules list raises ValueError."""
        mock_policy = {"rules": [], "description": "Empty rules"}
        mock_load_policy.return_value = mock_policy

        with pytest.raises(
            ValueError, match="'rules' must be a non-empty list in the policy."
        ):
            policy_loader.load_micro_proposal_policy()

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_micro_proposal_policy_wrong_rules_type(self, mock_load_policy):
        """Test loading policy with wrong type for rules raises ValueError."""
        mock_policy = {"rules": "not_a_list", "description": "Wrong type"}
        mock_load_policy.return_value = mock_policy

        with pytest.raises(
            ValueError, match="'rules' must be a non-empty list in the policy."
        ):
            policy_loader.load_micro_proposal_policy()


class TestPolicyLoaderIntegration:
    """Integration tests for policy loader functionality."""

    def test_directory_paths_are_correct(self):
        """Test that the directory paths are set correctly."""
        assert policy_loader.CONSTITUTION_DIR == Path(".intent/charter")
        assert policy_loader.GOVERNANCE_DIR == Path(
            ".intent/charter/policies/governance"
        )
        assert policy_loader.AGENT_DIR == Path(".intent/charter/policies/agent")

    def test_module_exports_correct_functions(self):
        """Test that the module exports the correct functions."""
        expected_exports = ["load_available_actions", "load_micro_proposal_policy"]
        assert policy_loader.__all__ == expected_exports
