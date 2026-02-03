# tests/unit/cli/test_cli_validation.py
# ID: tests.unit.cli.test_cli_validation
"""
Unit tests for CLI validation framework.

Tests constitutional rule enforcement at command registration time.
"""

from __future__ import annotations

import pytest

from shared.cli_framework import (
    ConstitutionalViolation,
    validate_action_name,
    validate_command_depth,
    validate_resource_name,
)


class TestResourceNameValidation:
    """Test resource name validation rules."""

    # ID: test_valid_resource_names
    def test_valid_resource_names(self):
        """Valid resource names should pass validation."""
        valid_names = ["database", "vectors", "code", "symbols", "admin"]

        for name in valid_names:
            validate_resource_name(name)  # Should not raise

    # ID: test_forbidden_layer_names
    def test_forbidden_layer_names(self):
        """Layer names (mind/body/will) should be rejected."""
        forbidden = ["mind", "body", "will", "manage", "check", "fix"]

        for name in forbidden:
            with pytest.raises(ConstitutionalViolation, match="forbidden"):
                validate_resource_name(name)

    # ID: test_uppercase_rejected
    def test_uppercase_rejected(self):
        """Uppercase resource names should be rejected."""
        with pytest.raises(ConstitutionalViolation, match="lowercase"):
            validate_resource_name("Database")

    # ID: test_invalid_characters
    def test_invalid_characters(self):
        """Special characters (except hyphens) should be rejected."""
        with pytest.raises(ConstitutionalViolation, match="alphanumeric"):
            validate_resource_name("data_base")

        with pytest.raises(ConstitutionalViolation, match="alphanumeric"):
            validate_resource_name("data.base")

    # ID: test_hyphens_allowed
    def test_hyphens_allowed(self):
        """Hyphens in resource names should be allowed."""
        validate_resource_name("my-resource")  # Should not raise


class TestActionNameValidation:
    """Test action name validation rules."""

    # ID: test_standard_verbs_pass
    def test_standard_verbs_pass(self, caplog):
        """Standard verbs should validate without warnings."""
        standard_verbs = ["sync", "query", "validate", "audit", "list"]

        for verb in standard_verbs:
            validate_action_name("database", verb)
            # Should log debug message, not warning

    # ID: test_non_standard_verbs_warn
    def test_non_standard_verbs_warn(self, caplog):
        """Non-standard verbs should trigger warnings."""
        validate_action_name("database", "foobar")

        # Should have warning in logs
        assert "non-standard" in caplog.text.lower()


class TestCommandDepthValidation:
    """Test command depth validation rules."""

    # ID: test_depth_2_valid
    def test_depth_2_valid(self):
        """Commands at depth=2 (resource action) should be valid."""
        validate_command_depth("database sync")
        validate_command_depth("vectors query")

    # ID: test_admin_depth_3_allowed
    def test_admin_depth_3_allowed(self):
        """Admin namespace should allow depth=3."""
        validate_command_depth("admin config sync")
        validate_command_depth("admin secrets get")

    # ID: test_non_admin_depth_3_rejected
    def test_non_admin_depth_3_rejected(self):
        """Non-admin commands at depth=3 should be rejected."""
        with pytest.raises(ConstitutionalViolation, match="depth=3"):
            validate_command_depth("database foo bar")

    # ID: test_depth_4_always_rejected
    def test_depth_4_always_rejected(self):
        """No command should exceed depth=3."""
        with pytest.raises(ConstitutionalViolation, match="exceeds maximum"):
            validate_command_depth("admin foo bar baz")

    # ID: test_depth_1_valid
    def test_depth_1_valid(self):
        """Single-word commands are valid (e.g., 'dev' workflow)."""
        validate_command_depth("dev")


class TestValidationIntegration:
    """Integration tests for validation framework."""

    # ID: test_full_validation_pipeline
    def test_full_validation_pipeline(self):
        """Test complete validation flow for a valid resource."""
        from shared.cli_framework.validation import validate_resource_module

        validate_resource_module(
            resource_name="database", module_path="body.cli.resources.database"
        )

    # ID: test_validation_rejects_bad_module_path
    def test_validation_rejects_bad_module_path(self):
        """Test that module path validation works."""
        from shared.cli_framework.validation import validate_resource_module

        with pytest.raises(ConstitutionalViolation, match="must be in"):
            validate_resource_module(
                resource_name="database", module_path="some.random.module"
            )
