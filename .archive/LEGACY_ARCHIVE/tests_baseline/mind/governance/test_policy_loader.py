# tests/mind/governance/test_policy_loader.py
import pytest


pytestmark = pytest.mark.legacy

from unittest.mock import patch

import yaml

# Import the module under test
from mind.governance import policy_loader


class TestLoadPolicyYaml:
    """Test cases for _load_policy_yaml function."""

    @patch("mind.governance.policy_loader.settings")
    def test_load_valid_yaml_file(self, mock_settings, tmp_path):
        """Test loading a valid YAML policy file."""
        # Mock settings to return our test file path
        mock_settings.REPO_PATH = tmp_path

        policy_content = {
            "actions": ["action1", "action2"],
            "rules": ["rule1", "rule2"],
        }
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text(yaml.dump(policy_content))

        # Mock get_path to return our test file
        mock_settings.get_path.return_value = policy_file

        # Test loading the file
        result = policy_loader._load_policy_yaml("test.policy")
        assert result == policy_content

    @patch("mind.governance.policy_loader.settings")
    def test_load_nonexistent_file(self, mock_settings, tmp_path):
        """Test loading a non-existent file raises ValueError."""
        mock_settings.REPO_PATH = tmp_path
        non_existent_file = tmp_path / "nonexistent.yaml"

        # Mock get_path to return non-existent file
        mock_settings.get_path.return_value = non_existent_file

        with pytest.raises(
            ValueError, match=f"Policy file not found: {non_existent_file}"
        ):
            policy_loader._load_policy_yaml("nonexistent.policy")

    @patch("mind.governance.policy_loader.settings")
    def test_load_invalid_yaml_format(self, mock_settings, tmp_path):
        """Test loading a file with invalid YAML format."""
        mock_settings.REPO_PATH = tmp_path
        invalid_yaml_file = tmp_path / "invalid.yaml"
        invalid_yaml_file.write_text("invalid: yaml: content: [")

        # Mock get_path to return our invalid file
        mock_settings.get_path.return_value = invalid_yaml_file

        with pytest.raises(ValueError, match="Failed to load policy 'invalid.policy'"):
            policy_loader._load_policy_yaml("invalid.policy")

    @patch("mind.governance.policy_loader.settings")
    def test_load_empty_yaml_file(self, mock_settings, tmp_path):
        """Test loading an empty YAML file returns empty dict."""
        mock_settings.REPO_PATH = tmp_path
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        # Mock get_path to return our empty file
        mock_settings.get_path.return_value = empty_file

        result = policy_loader._load_policy_yaml("empty.policy")
        assert result == {}

    @patch("mind.governance.policy_loader.settings")
    def test_load_yaml_with_non_dict_content(self, mock_settings, tmp_path):
        """Test loading YAML that doesn't result in a dictionary."""
        mock_settings.REPO_PATH = tmp_path
        list_yaml_file = tmp_path / "list.yaml"
        list_yaml_file.write_text("- item1\n- item2")

        # Mock get_path to return our list file
        mock_settings.get_path.return_value = list_yaml_file

        with pytest.raises(
            ValueError, match=f"Policy file must be a dictionary: {list_yaml_file}"
        ):
            policy_loader._load_policy_yaml("list.policy")

    @patch("mind.governance.policy_loader.settings")
    @patch("mind.governance.policy_loader.logger")
    def test_logging_on_file_not_found(self, mock_logger, mock_settings, tmp_path):
        """Test that appropriate logging occurs when file is not found."""
        mock_settings.REPO_PATH = tmp_path
        non_existent_file = tmp_path / "nonexistent.yaml"

        # Mock get_path to return non-existent file
        mock_settings.get_path.return_value = non_existent_file

        with pytest.raises(ValueError):
            policy_loader._load_policy_yaml("nonexistent.policy")

        mock_logger.error.assert_called()

    @patch("mind.governance.policy_loader.settings")
    @patch("mind.governance.policy_loader.logger")
    def test_logging_on_yaml_loading_error(self, mock_logger, mock_settings, tmp_path):
        """Test that appropriate logging occurs when YAML loading fails."""
        mock_settings.REPO_PATH = tmp_path
        invalid_yaml_file = tmp_path / "invalid.yaml"
        invalid_yaml_file.write_text("invalid: yaml: [")

        # Mock get_path to return our invalid file
        mock_settings.get_path.return_value = invalid_yaml_file

        with pytest.raises(ValueError):
            policy_loader._load_policy_yaml("invalid.policy")

        mock_logger.error.assert_called()


class TestLoadAvailableActions:
    """Test cases for load_available_actions function."""

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_valid_actions_policy(self, mock_load_policy):
        """Test loading a valid available actions policy."""
        mock_policy = {
            "planner_actions": ["create_file", "modify_file", "delete_file"],
            "version": "1.0",
        }
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_available_actions()

        assert result == {"actions": ["create_file", "modify_file", "delete_file"]}
        mock_load_policy.assert_called_once_with("charter.policies.agent_governance")

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_actions_policy_fallback(self, mock_load_policy):
        """Test loading policy with fallback to 'actions' key."""
        mock_policy = {
            "actions": ["create_file", "modify_file"],
            "version": "1.0",
        }
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_available_actions()

        assert result == {"actions": ["create_file", "modify_file"]}

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_actions_policy_missing_actions(self, mock_load_policy):
        """Test loading policy with missing actions returns empty list."""
        mock_policy = {"version": "1.0"}
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_available_actions()

        assert result == {"actions": []}

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_actions_policy_empty_actions(self, mock_load_policy):
        """Test loading policy with empty actions list."""
        mock_policy = {"planner_actions": [], "version": "1.0"}
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_available_actions()

        assert result == {"actions": []}


class TestLoadMicroProposalPolicy:
    """Test cases for load_micro_proposal_policy function."""

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_valid_micro_proposal_policy(self, mock_load_policy):
        """Test loading a valid micro proposal policy."""
        mock_policy = {
            "policy_id": "test-policy",
            "autonomy_lanes": {
                "micro_proposals": {
                    "description": "Micro proposal validation rules",
                    "safe_paths": ["/src/", "/tests/"],
                    "forbidden_paths": ["/config/", "/secrets/"],
                    "allowed_actions": ["create", "modify", "delete"],
                }
            },
        }
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_micro_proposal_policy()

        assert result["policy_id"] == "test-policy"
        assert len(result["rules"]) == 2
        assert result["rules"][0]["id"] == "safe_paths"
        assert result["rules"][0]["allowed_paths"] == ["/src/", "/tests/"]
        assert result["rules"][0]["forbidden_paths"] == ["/config/", "/secrets/"]
        assert result["rules"][1]["id"] == "safe_actions"
        assert result["rules"][1]["allowed_actions"] == ["create", "modify", "delete"]

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_micro_proposal_policy_missing_lanes(self, mock_load_policy):
        """Test loading policy with missing autonomy lanes."""
        mock_policy = {}  # No policy_id or lanes
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_micro_proposal_policy()

        # When lanes are missing, function returns early with only "rules" key
        assert result == {"rules": []}

    @patch("mind.governance.policy_loader._load_policy_yaml")
    def test_load_micro_proposal_policy_empty_lanes(self, mock_load_policy):
        """Test loading policy with empty micro_proposals."""
        mock_policy = {
            "policy_id": "test-policy",
            "autonomy_lanes": {"micro_proposals": {}},
        }
        mock_load_policy.return_value = mock_policy

        result = policy_loader.load_micro_proposal_policy()

        # When lanes dict exists but is empty, it's still falsy so returns early
        assert result == {"rules": []}


class TestPolicyLoaderIntegration:
    """Integration tests for policy loader functionality."""

    def test_module_exports_correct_functions(self):
        """Test that the module exports the correct functions."""
        expected_exports = ["load_available_actions", "load_micro_proposal_policy"]
        assert policy_loader.__all__ == expected_exports
