# tests/shared/test_action_types.py
"""
Tests for ActionResult and atomic action framework.

Validates the universal result contract and metadata system.
"""

import pytest

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import ActionMetadata, atomic_action, get_action_metadata


class TestActionResult:
    """Test suite for ActionResult dataclass."""

    def test_minimal_action_result(self):
        """ActionResult can be created with minimal required fields."""
        result = ActionResult(
            action_id="test.action",
            ok=True,
            data={"count": 42},
        )

        assert result.action_id == "test.action"
        assert result.ok is True
        assert result.data == {"count": 42}
        assert result.duration_sec == 0.0
        assert result.impact is None
        assert result.logs == []
        assert result.warnings == []
        assert result.suggestions == []

    def test_full_action_result(self):
        """ActionResult can be created with all optional fields."""
        result = ActionResult(
            action_id="fix.ids",
            ok=True,
            data={"ids_assigned": 10},
            duration_sec=1.5,
            impact=ActionImpact.WRITE_METADATA,
            logs=["Started processing", "Completed processing"],
            warnings=["Using fallback method"],
            suggestions=["Run check.ids to verify"],
        )

        assert result.action_id == "fix.ids"
        assert result.ok is True
        assert result.data == {"ids_assigned": 10}
        assert result.duration_sec == 1.5
        assert result.impact == ActionImpact.WRITE_METADATA
        assert len(result.logs) == 2
        assert len(result.warnings) == 1
        assert len(result.suggestions) == 1

    def test_validation_rejects_empty_action_id(self):
        """ActionResult validation rejects empty action_id."""
        with pytest.raises(ValueError, match="action_id must be non-empty string"):
            ActionResult(
                action_id="",
                ok=True,
                data={},
            )

    def test_validation_rejects_non_dict_data(self):
        """ActionResult validation rejects non-dict data."""
        with pytest.raises(ValueError, match="data must be a dict"):
            ActionResult(
                action_id="test.action",
                ok=True,
                data="not a dict",  # type: ignore
            )

    def test_validation_rejects_non_bool_ok(self):
        """ActionResult validation rejects non-boolean ok."""
        with pytest.raises(ValueError, match="ok must be a boolean"):
            ActionResult(
                action_id="test.action",
                ok="true",  # type: ignore
                data={},
            )


class TestActionImpact:
    """Test suite for ActionImpact enum."""

    def test_all_impact_types_exist(self):
        """All expected impact types are defined."""
        assert ActionImpact.READ_ONLY.value == "read-only"
        assert ActionImpact.WRITE_METADATA.value == "write-metadata"
        assert ActionImpact.WRITE_CODE.value == "write-code"
        assert ActionImpact.WRITE_DATA.value == "write-data"


class TestAtomicActionDecorator:
    """Test suite for @atomic_action decorator."""

    def test_decorator_attaches_metadata(self):
        """Decorator attaches ActionMetadata to function."""

        @atomic_action(
            action_id="test.action",
            intent="Test action for unit tests",
            impact=ActionImpact.READ_ONLY,
            policies=["test_policy"],
            category="tests",
        )
        async def test_function() -> ActionResult:
            return ActionResult(
                action_id="test.action",
                ok=True,
                data={},
            )

        metadata = get_action_metadata(test_function)

        assert metadata is not None
        assert metadata.action_id == "test.action"
        assert metadata.intent == "Test action for unit tests"
        assert metadata.impact == ActionImpact.READ_ONLY
        assert metadata.policies == ["test_policy"]
        assert metadata.category == "tests"

    def test_decorated_function_executes_normally(self):
        """Decorated function still executes and returns result."""

        @atomic_action(
            action_id="test.execution",
            intent="Test execution",
            impact=ActionImpact.READ_ONLY,
            policies=[],
        )
        async def test_function(value: int) -> ActionResult:
            return ActionResult(
                action_id="test.execution",
                ok=True,
                data={"doubled": value * 2},
            )

        # Execute the function
        import asyncio

        result = asyncio.run(test_function(21))

        assert result.action_id == "test.execution"
        assert result.ok is True
        assert result.data == {"doubled": 42}

    def test_get_action_metadata_returns_none_for_undecorated(self):
        """get_action_metadata returns None for non-decorated functions."""

        async def regular_function():
            pass

        metadata = get_action_metadata(regular_function)
        assert metadata is None

    def test_metadata_is_frozen(self):
        """ActionMetadata is immutable (frozen dataclass)."""

        metadata = ActionMetadata(
            action_id="test.frozen",
            intent="Test immutability",
            impact=ActionImpact.READ_ONLY,
            policies=[],
        )

        # Should not be able to modify
        with pytest.raises(Exception):  # FrozenInstanceError
            metadata.action_id = "modified"  # type: ignore


class TestBackwardCompatibility:
    """Test backward compatibility aliases."""

    def test_command_result_alias_exists(self):
        """CommandResult alias exists for backward compatibility."""
        from shared.action_types import CommandResult

        # Should be the same class as ActionResult
        result = CommandResult(
            action_id="test.compat",
            ok=True,
            data={},
        )

        assert isinstance(result, ActionResult)
        assert result.action_id == "test.compat"
