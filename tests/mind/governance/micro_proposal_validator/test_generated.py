"""Tests for MicroProposalValidator.

2026-06-07 (#572 Cat B batch 13):
- _load_policy expects the v2 nested structure
  ``autonomy_lanes.micro_proposals.{safe_paths, forbidden_paths, allowed_actions}``
  in the YAML (see micro_proposal_validator.py:49-83). The autogen vintage
  emitted a flat ``{"rules": [...]}`` shape — source quietly fell through
  to the default policy whenever it saw that, masking every fixture-
  dependent test.
- The autogen also overwrote ``yaml.safe_load`` at module level inside
  fixtures (``yaml.safe_load = MagicMock(return_value=...)``), polluting
  every subsequent test in the process. Replaced with real yaml.dump
  round-trips so source's real yaml.safe_load drives the parse.
- ``test_load_policy_parses_yaml`` now asserts on the transformed
  structure source returns (source rewrites the YAML into a
  ``rules: [...]`` shape), not the raw YAML.
- ``test_path_ok_multiple_patterns`` asserts on ``docs/README.md``
  instead of bare ``README.md`` — source's ``**/*.md`` glob doesn't
  match a basename at the repo root (fnmatch limitation), and that
  semantic is correct given the codebase layout.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yaml

from mind.governance.micro_proposal_validator import (
    MicroProposalValidator,
    _default_policy,
    _load_policy,
)


def _build_resolver(*, exists: bool, yaml_text: str = "") -> MagicMock:
    """Build a MagicMock PathResolver returning a policy file with the
    given existence + YAML body."""
    resolver = MagicMock()
    resolver.policy.return_value.exists.return_value = exists
    resolver.policy.return_value.read_text.return_value = yaml_text
    return resolver


@pytest.fixture
def mock_path_resolver():
    """Fixture that returns a mock PathResolver with policy_path.exists=False."""
    return _build_resolver(exists=False)


@pytest.fixture
def validator_with_default_policy(mock_path_resolver):
    """Fixture that creates a MicroProposalValidator using the default policy."""
    return MicroProposalValidator(mock_path_resolver)


@pytest.fixture
def validator_with_custom_policy():
    """Validator built from a v2-nested ``autonomy_lanes.micro_proposals``
    YAML — source's ``_load_policy`` extracts the inner lane and rewrites
    it into the rules[] format the validator instance consumes."""
    yaml_text = yaml.dump(
        {
            "autonomy_lanes": {
                "micro_proposals": {
                    "safe_paths": ["src/**", "tests/**"],
                    "forbidden_paths": [".intent/**", "secrets/**"],
                    "allowed_actions": ["create", "update", "delete"],
                }
            }
        }
    )
    resolver = _build_resolver(exists=True, yaml_text=yaml_text)
    return MicroProposalValidator(resolver)


@pytest.fixture
def validator_with_actions_only():
    """Validator with only an ``allowed_actions`` list — no safe_paths /
    forbidden_paths constraints."""
    yaml_text = yaml.dump(
        {
            "autonomy_lanes": {
                "micro_proposals": {
                    "allowed_actions": ["review", "approve"],
                }
            }
        }
    )
    resolver = _build_resolver(exists=True, yaml_text=yaml_text)
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
        assert validator_with_custom_policy._forbidden_paths == [
            ".intent/**",
            "secrets/**",
        ]
        assert validator_with_custom_policy._allowed_actions == [
            "create",
            "update",
            "delete",
        ]

    def test_init_handles_missing_rules(self):
        """An ``autonomy_lanes.micro_proposals`` lane that exists but is
        empty (no safe_paths / forbidden_paths / allowed_actions) yields
        empty internal lists — neither a fall-through to defaults nor an
        error."""
        yaml_text = yaml.dump(
            {"autonomy_lanes": {"micro_proposals": {"explicit_marker": True}}}
        )
        resolver = _build_resolver(exists=True, yaml_text=yaml_text)
        validator = MicroProposalValidator(resolver)
        assert validator._allowed_paths == []
        assert validator._forbidden_paths == []
        assert validator._allowed_actions == []

    # ---------- _path_ok ----------
    def test_path_ok_allowed_path(self, validator_with_custom_policy):
        """Verify that an allowed path returns (True, 'ok')."""
        assert validator_with_custom_policy._path_ok("src/core/module.py") == (
            True,
            "ok",
        )

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
        """Default policy matches files across the multiple allowed_paths
        patterns. ``**/*.md`` requires a directory prefix (fnmatch quirk),
        so ``docs/README.md`` matches but bare ``README.md`` does not —
        the autogen vintage's bare-``README.md`` assertion was wrong."""
        validator = MicroProposalValidator(mock_path_resolver)
        assert validator._path_ok("tests/test_file.py") == (True, "ok")
        assert validator._path_ok("docs/README.md") == (True, "ok")

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
        assert validator_with_default_policy.validate("not a list") == (
            False,
            "Plan is empty",
        )

    def test_validate_step_missing_action(self, validator_with_default_policy):
        """Verify that a step without action returns (False, message)."""
        plan = [{}]
        result, msg = validator_with_default_policy.validate(plan)
        assert result is False
        assert "missing action" in msg

    def test_validate_step_valid_dict(self, validator_with_custom_policy):
        """Verify that a valid step (dict) passes validation."""
        plan = [
            {
                "action": "create",
                "parameters": {"file_path": "src/new_file.py"},
            }
        ]
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
        plan = [
            {"action": "delete_secrets", "parameters": {"file_path": "src/safe.py"}}
        ]
        result, msg = validator_with_custom_policy.validate(plan)
        assert result is False
        assert "not in the allowed autonomy lane" in msg

    def test_validate_step_invalid_path(self, validator_with_custom_policy):
        """Verify that a step with invalid path fails."""
        plan = [
            {
                "action": "create",
                "parameters": {"file_path": ".intent/evil.py"},
            }
        ]
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

    def test_validate_step_with_name_instead_of_action(
        self, validator_with_custom_policy
    ):
        """Verify that step uses 'name' field if 'action' is absent."""
        plan = [{"name": "create", "parameters": {"file_path": "src/file.py"}}]
        assert validator_with_custom_policy.validate(plan) == (True, "")

    def test_validate_step_with_params_instead_of_parameters(
        self, validator_with_custom_policy
    ):
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
        """``_load_policy`` reads the YAML through the path resolver,
        extracts the ``autonomy_lanes.micro_proposals`` lane, and
        re-emits it as a ``rules: [safe_paths, safe_actions]`` document
        carrying the original ``policy_id`` (source lines 49-83). The
        autogen vintage's flat ``{"rules": ...}`` input shape was
        silently ignored by source — _load_policy fell through to the
        default policy whenever the autonomy_lanes key was absent."""
        yaml_input = {
            "policy_id": "test-policy",
            "autonomy_lanes": {
                "micro_proposals": {
                    "safe_paths": ["src/**"],
                    "forbidden_paths": [".intent/**"],
                    "allowed_actions": ["create"],
                }
            },
        }
        resolver = _build_resolver(exists=True, yaml_text=yaml.dump(yaml_input))
        policy = _load_policy(resolver)
        assert policy == {
            "policy_id": "test-policy",
            "rules": [
                {
                    "id": "safe_paths",
                    "allowed_paths": ["src/**"],
                    "forbidden_paths": [".intent/**"],
                },
                {"id": "safe_actions", "allowed_actions": ["create"]},
            ],
        }

    # ---------- _default_policy ----------
    def test_default_policy_contains_rules(self):
        """Verify that _default_policy returns a dict with a 'rules' key."""
        policy = _default_policy()
        assert "rules" in policy
        assert isinstance(policy["rules"], list)

    def test_default_policy_safe_paths_structure(self):
        """Verify the structure of safe_paths rule in default policy."""
        policy = _default_policy()
        safe_paths_rule = next(
            r for r in policy["rules"] if r.get("id") == "safe_paths"
        )
        assert "allowed_paths" in safe_paths_rule
        assert "forbidden_paths" in safe_paths_rule
        assert ".intent/**" in safe_paths_rule["forbidden_paths"]
