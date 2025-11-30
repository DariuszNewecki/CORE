# tests/body/cli/commands/fix/test_migrated_actions.py
"""
Tests for migrated actions using ActionResult and @atomic_action.

Validates that fix.ids and fix.headers work correctly with the new
atomic action framework.
"""

import pytest
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import get_action_metadata


class TestFixIdsMigration:
    """Test suite for migrated fix.ids action."""

    @pytest.mark.asyncio
    async def test_fix_ids_has_metadata(self):
        """fix_ids_internal has atomic action metadata."""
        from body.cli.commands.fix.metadata import fix_ids_internal

        metadata = get_action_metadata(fix_ids_internal)

        assert metadata is not None
        assert metadata.action_id == "fix.ids"
        assert metadata.intent == "Assign stable UUIDs to untagged public symbols"
        assert metadata.impact == ActionImpact.WRITE_METADATA
        assert "symbol_identification" in metadata.policies
        assert metadata.category == "fixers"

    @pytest.mark.asyncio
    async def test_fix_ids_returns_action_result(self):
        """fix_ids_internal returns ActionResult."""
        from body.cli.commands.fix.metadata import fix_ids_internal

        result = await fix_ids_internal(write=False)

        assert isinstance(result, ActionResult)
        assert result.action_id == "fix.ids"
        assert isinstance(result.ok, bool)
        assert isinstance(result.data, dict)
        assert "ids_assigned" in result.data
        assert "dry_run" in result.data
        assert result.duration_sec >= 0

    @pytest.mark.asyncio
    async def test_fix_ids_dry_run_mode(self):
        """fix_ids_internal respects dry-run mode."""
        from body.cli.commands.fix.metadata import fix_ids_internal

        result = await fix_ids_internal(write=False)

        assert result.data["dry_run"] is True
        assert result.data["mode"] == "dry-run"

    @pytest.mark.asyncio
    async def test_fix_ids_write_mode(self):
        """fix_ids_internal respects write mode."""
        from body.cli.commands.fix.metadata import fix_ids_internal

        result = await fix_ids_internal(write=True)

        assert result.data["dry_run"] is False
        assert result.data["mode"] == "write"


class TestFixHeadersMigration:
    """Test suite for migrated fix.headers action."""

    @pytest.mark.asyncio
    async def test_fix_headers_has_metadata(self):
        """fix_headers_internal has atomic action metadata."""
        from body.cli.commands.fix.code_style import fix_headers_internal

        metadata = get_action_metadata(fix_headers_internal)

        assert metadata is not None
        assert metadata.action_id == "fix.headers"
        assert (
            metadata.intent
            == "Ensure all Python files have constitutionally compliant headers"
        )
        assert metadata.impact == ActionImpact.WRITE_METADATA
        assert "file_headers" in metadata.policies
        assert metadata.category == "fixers"

    @pytest.mark.asyncio
    async def test_fix_headers_returns_action_result(self):
        """fix_headers_internal returns ActionResult."""
        from body.cli.commands.fix.code_style import fix_headers_internal

        result = await fix_headers_internal(write=False)

        assert isinstance(result, ActionResult)
        assert result.action_id == "fix.headers"
        assert isinstance(result.ok, bool)
        assert isinstance(result.data, dict)
        assert "violations_found" in result.data
        assert "files_scanned" in result.data
        assert "dry_run" in result.data
        assert result.duration_sec >= 0

    @pytest.mark.asyncio
    async def test_fix_headers_dry_run_mode(self):
        """fix_headers_internal respects dry-run mode."""
        from body.cli.commands.fix.code_style import fix_headers_internal

        result = await fix_headers_internal(write=False)

        assert result.data["dry_run"] is True
        # In dry-run with violations, ok should be False
        # (violations exist but not fixed)

    @pytest.mark.asyncio
    async def test_fix_headers_includes_suggestions(self):
        """fix_headers_internal includes helpful suggestions."""
        from body.cli.commands.fix.code_style import fix_headers_internal

        # Dry-run mode
        result = await fix_headers_internal(write=False)

        if not result.ok and result.data["violations_found"] > 0:
            # Should suggest running with --write
            assert len(result.suggestions) > 0
            assert any("--write" in s for s in result.suggestions)


class TestBackwardCompatibility:
    """Ensure migrations don't break existing code."""

    @pytest.mark.asyncio
    async def test_command_result_alias_still_works(self):
        """CommandResult alias still works for backward compatibility."""
        from shared.action_types import CommandResult

        # Should still be able to use CommandResult
        result = CommandResult(
            action_id="test.compat",
            ok=True,
            data={},
        )

        assert result.action_id == "test.compat"
        # It's actually an ActionResult under the hood
        assert isinstance(result, ActionResult)
