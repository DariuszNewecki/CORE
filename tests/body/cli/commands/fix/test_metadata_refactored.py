# tests/body/cli/commands/fix/test_metadata_refactored.py
"""
Tests for the refactored metadata commands.
Updated to test against the ActionResult contract (the new standard).
"""

import pytest

from body.cli.commands.fix.metadata import fix_ids_internal

# CHANGED: Import ActionResult from action_types, not CommandResult from cli_types
from shared.action_types import ActionResult


class TestFixIdsInternal:
    """Tests for fix_ids_internal using ActionResult pattern."""

    @pytest.mark.asyncio
    async def test_returns_action_result(self):
        """fix_ids_internal should return an ActionResult instance."""
        result = await fix_ids_internal(write=False)

        assert isinstance(result, ActionResult)
        # Check action_id (canonical) and name (property alias)
        assert result.action_id == "fix.ids"
        assert result.name == "fix.ids"

    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Dry run should be indicated in result data."""
        result = await fix_ids_internal(write=False)

        assert result.data["dry_run"] is True
        assert result.data["mode"] == "dry-run"
        assert "ids_assigned" in result.data

    @pytest.mark.asyncio
    async def test_write_mode(self):
        """Write mode should be indicated in result data."""
        result = await fix_ids_internal(write=True)

        assert result.data["dry_run"] is False
        assert result.data["mode"] == "write"
        assert "ids_assigned" in result.data

    @pytest.mark.asyncio
    async def test_success_result(self):
        """Successful execution should set ok=True."""
        result = await fix_ids_internal(write=False)
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_has_duration(self):
        """Result should include execution duration."""
        result = await fix_ids_internal(write=False)
        assert result.duration_sec >= 0.0
        assert isinstance(result.duration_sec, float)


class TestActionResultContract:
    """Tests that validate the ActionResult contract itself."""

    def test_action_result_requires_id(self):
        """ActionResult must have a non-empty action_id."""
        with pytest.raises(ValueError, match="action_id must be non-empty string"):
            ActionResult(action_id="", ok=True, data={})

    def test_action_result_requires_dict_data(self):
        """ActionResult.data must be a dict."""
        with pytest.raises(ValueError, match="data must be a dict"):
            ActionResult(action_id="test", ok=True, data="not a dict")

    def test_action_result_defaults(self):
        """ActionResult should have sensible defaults."""
        result = ActionResult(action_id="test", ok=True, data={})
        assert result.duration_sec == 0.0
        assert result.logs == []

    def test_action_result_with_logs(self):
        """ActionResult can include debug logs."""
        result = ActionResult(
            action_id="test",
            ok=False,
            data={"error": "something broke"},
            logs=["Step 1", "Step 2", "Error occurred"],
        )
        assert len(result.logs) == 3
        assert result.ok is False
