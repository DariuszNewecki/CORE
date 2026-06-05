import pytest
from unittest.mock import MagicMock, PropertyMock
from mind.governance.micro_proposal_validator import MicroProposalValidator, _default_policy, _load_policy


@pytest.fixture
def mock_path_resolver():
    """Fixture that returns a mock PathResolver with a policy method."""
    resolver = MagicMock()
    resolver.policy.return_value.exists.return_value = False
    return resolver


@pytest.fixture
def validator_with_default_policy(mock_path_resolver):
    """Fixture that creates a MicroProposalValidator using the default policy."""
    return MicroProposalValidator(mock_path_resolver)


@pytest.fixture
def validator_with_custom_policy():
    """Fixture that creates a MicroProposalValidator with a custom policy loaded from a YAML file."""
    resolver = MagicMock()
    policy_data = {
        "rules": [
            {
                "id": "safe_paths",
                "allowed_paths": ["src/**", "tests/**"],
                "forbidden_paths": [".intent/**", "secrets/**"],
            },
            {
                "id": "safe_actions",
                "allowed_actions": ["create", "update", "delete"],
            },
        ]
    }
    resolver.policy.return_value.exists.return_value = True
    import yaml
    yaml.safe_load = MagicMock(return_value=policy_data)
    resolver.policy.return_value.read_text.return_value = ""
    return MicroProposalValidator(resolver)


@pytest.fixture
def validator_with_actions_only():
    """Fixture creating a validator with only actions rule (no paths rule)."""
    resolver = MagicMock()
    policy_data = {
        "rules": [
            {
                "id": "safe_actions",
                "allowed_actions": ["review", "approve"],
            },
        ]
    }
    resolver.policy.return_value.exists.return_value = True
    import yaml
    yaml.safe_load = MagicMock(return_value=policy_data)
    resolver.policy.return_value.read_text.return_value = ""
    return MicroProposalValidator(resolver)


class TestMicroProposalValidator:
    """Tests for the MicroProposalValidator class."""

    # ---------- __init__ ----------
    def test_init_uses_default_policy_when_no_file(self, mock_path_resolver):
        """Verify that __init__ falls back to _default_policy when policy file is missing."""
        validator = MicroProposalValidator(mock_path_resolver)
        expected_policy = _default_policy()
        assert validator.policy == expected_policy

    def test_init_loads_custom_policy(self, validator_with_custom_policy):
        """Verify that __init__ loads custom policy when policy file exists."""
        assert validator_with_custom_policy._allowed_paths == ["src/**", "tests/**"]
        assert validator_with_custom_policy._forbidden_paths == [".intent/**", "secrets/**"]
        assert validator_with_custom_policy._allowed_actions == ["create", "update", "delete"]

    def test_init_handles_missing_rules(self, mock_path_resolver):
        """Verify that __init__ gracefully handles missing 'rules' key."""
        resolver = mock_path_resolver
        # Override default behaviour: assume policy path exists but content has no rules
        resolver.policy.return_value.exists.return_value = True
        import yaml
        yaml.safe_load = MagicMock(return_value={})
        resolver.policy.return_value.read_text.return_value = ""
        validator = MicroProposalValidator(resolver)
        assert validator._allowed_paths == []
        assert validator._forbidden_paths == []
        assert validator._allowed_actions == []

    # ---------- _path_ok ----------
    def test_path_ok_allowed_path(self, validator_with_custom_policy):
        """Verify that an allowed path returns (True, 'ok')."""
        assert validator_with_custom_policy._path_ok("src/core/module.py") == (True, "ok")

    def test_path_ok_forbidden_path(self, validator_with_custom_policy):
        """Verify that a forbidden path returns (False, message)."""
        result, msg = validator_with_custom_policy._path_ok(".intent/config.yaml")
        assert result is False
        assert "explicitly forbidden" in msg

    def test_path_ok_not_in_allowed_paths(self, validator_with_custom_policy):
        """Verify path not in allowed list returns (False, message)."""
        result, msg = validator_with_custom_policy._path_ok("externals/something.txt")
        assert result is False
        assert "not in allowed paths" in msg

    def test_path_ok_allowed_paths_empty_allows_any(self, validator_with_actions_only):
        """Verify that when allowed_paths is empty, any path is accepted."""
        assert validator_with_actions_only._path_ok("any/path.py") == (True, "ok")

    def test_path_ok_multiple_patterns(self, mock_path_resolver):
        """Verify path matching with multiple allowed patterns."""
        validator = MicroProposalValidator(mock_path_resolver)
        # Default policy has multiple allowed patterns
        assert validator._path_ok("tests/test_file.py") == (True, "ok")
        assert validator._path_ok("README.md") == (True, "ok")

    # ---------- _action_ok ----------
    def test_action_ok_allowed_action(self, validator_with_custom_policy):
        """Verify that an allowed action returns (True, 'ok')."""
        assert validator_with_custom_policy._action_ok("create") == (True, "ok")

    def test_action_ok_not_allowed_action(self, validator_with_custom_policy):
        """Verify that a disallowed action returns (False, message)."""
        result, msg = validator_with_custom_policy._action_ok("publish")
        assert result is False
        assert "not in the allowed autonomy lane" in msg

    def test_action_ok_no_allowed_actions(self, validator_with_default_policy):
        """Verify that when allowed_actions is empty, any action is accepted."""
        assert validator_with_default_policy._action_ok("anything") == (True, "ok")

    # ---------- validate ----------
    def test_validate_empty_plan(self, validator_with_default_policy):
        """Verify that empty plan returns (False, 'Plan is empty')."""
        assert validator_with_default_policy.validate([]) == (False, "Plan is empty")

    def test_validate_non_list(self, validator_with_default_policy):
        """Verify that non-list plan returns (False, 'Plan is empty')."""
        assert validator_with_default_policy.validate("not a list") == (False, "Plan is empty")

    def test_validate_step_missing_action(self, validator_with_default_policy):
        """Verify that a step without action returns (False, message)."""
        plan = [{}]
        result, msg = validator_with_default_policy.validate(plan)
        assert result is False
        assert "missing action" in msg

    def test_validate_step_valid_dict(self, validator_with_custom_policy):
        """Verify that a valid step (dict) passes validation."""
        plan = [{
            "action": "create",
            "parameters": {"file_path": "src/new_file.py"},
        }]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    def test_validate_step_valid_pydantic(self, validator_with_custom_policy):
        """Verify that a Pydantic-like object with model_dump passes validation."""
        class MockStep:
            def model_dump(self):
                return {
                    "action": "update",
                    "parameters": {"file_path": "tests/test_update.py"},
                }
        plan = [MockStep()]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    def test_validate_step_invalid_action(self, validator_with_custom_policy):
        """Verify that a step with invalid action fails."""
        plan = [{"action": "delete_secrets", "parameters": {"file_path": "src/safe.py"}}]
        result, msg = validator_with_custom_policy.validate(plan)
        assert result is False
        assert "not in the allowed autonomy lane" in msg

    def test_validate_step_invalid_path(self, validator_with_custom_policy):
        """Verify that a step with invalid path fails."""
        plan = [{
            "action": "create",
            "parameters": {"file_path": ".intent/evil.py"},
        }]
        result, msg = validator_with_custom_policy.validate(plan)
        assert result is False
        assert "explicitly forbidden" in msg

    def test_validate_multiple_steps_all_valid(self, validator_with_custom_policy):
        """Verify that multiple valid steps pass."""
        plan = [
            {"action": "create", "parameters": {"file_path": "src/a.py"}},
            {"action": "update", "parameters": {"file_path": "tests/b.py"}},
            {"action": "delete", "parameters": {"file_path": "src/c.py"}},
        ]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    def test_validate_step_with_name_instead_of_action(self, validator_with_custom_policy):
        """Verify that step uses 'name' field if 'action' is absent."""
        plan = [{"name": "create", "parameters": {"file_path": "src/file.py"}}]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    def test_validate_step_with_params_instead_of_parameters(self, validator_with_custom_policy):
        """Verify that step uses 'params' field if 'parameters' is absent."""
        plan = [{"action": "create", "params": {"file_path": "src/file.py"}}]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    def test_validate_step_path_not_string_ignored(self, validator_with_custom_policy):
        """Verify that if file_path is not a string (e.g. None), path validation is skipped."""
        plan = [{"action": "create", "parameters": {"file_path": None}}]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    # ---------- _load_policy ----------
    def test_load_policy_missing_file_falls_back(self):
        """Verify that _load_policy returns default policy when file does not exist."""
        resolver = MagicMock()
        resolver.policy.return_value.exists.return_value = False
        policy = _load_policy(resolver)
        assert policy == _default_policy()

    def test_load_policy_parses_yaml(self):
        """Verify that _load_policy correctly parses YAML content."""
        resolver = MagicMock()
        resolver.policy.return_value.exists.return_value = True
        from io import StringIO
        import yaml
        yaml_content = {"rules": [{"id": "test", "value": 42}]}
        resolver.policy.return_value.read_text.return_value = yaml.dump(yaml_content)
        policy = _load_policy(resolver)
        assert policy == yaml_content

    # ---------- _default_policy ----------
    def test_default_policy_contains_rules(self):
        """Verify that _default_policy returns a dict with a 'rules' key."""
        policy = _default_policy()
        assert "rules" in policy
        assert isinstance(policy["rules"], list)

    def test_default_policy_safe_paths_structure(self):
        """Verify the structure of safe_paths rule in default policy."""
        policy = _default_policy()
        safe_paths_rule = next(r for r in policy["rules"] if r.get("id") == "safe_paths")
        assert "allowed_paths" in safe_paths_rule
        assert "forbidden_paths" in safe_paths_rule
        assert ".intent/**" in safe_paths_rule["forbidden_paths"]
