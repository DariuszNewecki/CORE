# tests/body/cli/commands/fix/test_metadata_refactored.py
"""
Tests for the refactored metadata commands.

This demonstrates how CommandResult makes testing trivial:
- No CLI framework needed
- No console output to capture
- Just call function, check result
"""

import pytest
from body.cli.commands.fix.metadata import fix_ids_internal
from shared.cli_types import CommandResult


class TestFixIdsInternal:
    """Tests for fix_ids_internal using CommandResult pattern."""

    @pytest.mark.asyncio
    async def test_returns_command_result(self):
        """fix_ids_internal should return a CommandResult instance."""
        result = await fix_ids_internal(write=False)

        assert isinstance(result, CommandResult)
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

        # Assuming the codebase has some files to process
        # The result should be successful
        assert result.ok is True
        assert result.data["ids_assigned"] >= 0  # Can be 0 if all IDs exist

    @pytest.mark.asyncio
    async def test_has_duration(self):
        """Result should include execution duration."""
        result = await fix_ids_internal(write=False)

        assert result.duration_sec >= 0.0
        assert isinstance(result.duration_sec, float)

    @pytest.mark.asyncio
    async def test_result_is_machine_readable(self):
        """Result should be easily convertible to JSON for machine parsing."""
        result = await fix_ids_internal(write=False)

        # This is what enables --format json
        result_dict = {
            "name": result.name,
            "ok": result.ok,
            "data": result.data,
            "duration_sec": result.duration_sec,
        }

        assert result_dict["name"] == "fix.ids"
        assert isinstance(result_dict["ok"], bool)
        assert isinstance(result_dict["data"], dict)
        assert isinstance(result_dict["duration_sec"], float)


class TestCommandResultContract:
    """Tests that validate the CommandResult contract itself."""

    def test_command_result_requires_name(self):
        """CommandResult must have a non-empty name."""
        with pytest.raises(ValueError, match="name must be non-empty"):
            CommandResult(name="", ok=True, data={})

    def test_command_result_requires_dict_data(self):
        """CommandResult.data must be a dict."""
        with pytest.raises(ValueError, match="data must be a dict"):
            CommandResult(name="test", ok=True, data="not a dict")

    def test_command_result_defaults(self):
        """CommandResult should have sensible defaults."""
        result = CommandResult(name="test", ok=True, data={})

        assert result.duration_sec == 0.0
        assert result.logs == []

    def test_command_result_with_logs(self):
        """CommandResult can include debug logs."""
        result = CommandResult(
            name="test",
            ok=False,
            data={"error": "something broke"},
            logs=["Step 1", "Step 2", "Error occurred"],
        )

        assert len(result.logs) == 3
        assert result.ok is False


# ============================================================================
# Integration test (requires actual codebase)
# ============================================================================


@pytest.mark.integration
class TestFixIdsIntegration:
    """
    Integration tests that actually run against the codebase.

    These are marked with @pytest.mark.integration so they can be
    skipped in fast unit test runs.
    """

    @pytest.mark.asyncio
    async def test_actual_id_assignment(self, tmp_path):
        """
        Test that fix_ids_internal actually assigns IDs.

        This would need a temporary test file or mock filesystem.
        For now, just validates the contract.
        """
        # This is where you'd set up a temp Python file
        # with a function missing an ID, run fix_ids_internal,
        # and verify the ID was added.

        result = await fix_ids_internal(write=False)

        # Basic contract validation
        assert result.ok is True
        assert "ids_assigned" in result.data

        # You could check that result.data["ids_assigned"] > 0
        # if you set up a test file that needs IDs


# ============================================================================
# Example of how orchestrators will use this
# ============================================================================


class TestOrchestrationPattern:
    """Demonstrates how workflow runners will use CommandResult."""

    @pytest.mark.asyncio
    async def test_collecting_multiple_results(self):
        """
        Workflow runners collect CommandResults from multiple commands.

        This is how dev.sync will work later.
        """
        # Simulate a workflow running multiple fix commands
        results = []

        # Step 1: fix ids
        result = await fix_ids_internal(write=False)
        results.append(result)

        # In real workflow, you'd call fix_headers_internal(), etc.
        # results.append(await fix_headers_internal(write=False))

        # Workflow analysis
        total_duration = sum(r.duration_sec for r in results)
        all_ok = all(r.ok for r in results)

        assert total_duration >= 0
        assert isinstance(all_ok, bool)

        # This data can be rendered by DevSyncReporter
        workflow_summary = {
            "total_steps": len(results),
            "successful": sum(1 for r in results if r.ok),
            "failed": sum(1 for r in results if not r.ok),
            "total_duration": total_duration,
            "results": [
                {
                    "name": r.name,
                    "ok": r.ok,
                    "data": r.data,
                }
                for r in results
            ],
        }

        assert workflow_summary["total_steps"] == 1  # Just fix ids for now
        assert workflow_summary["successful"] <= workflow_summary["total_steps"]
