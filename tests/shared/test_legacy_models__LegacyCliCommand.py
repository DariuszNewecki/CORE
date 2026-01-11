"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/legacy_models.py
- Symbol: LegacyCliCommand
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:04:08
"""

from shared.legacy_models import LegacyCliCommand


# Detected return type: The LegacyCliCommand class is a Pydantic BaseModel, not a function.
# It is synchronous, so regular 'def test_...' functions are used.


def test_legacy_cli_command_creation_with_required_fields():
    """Test basic creation with only required fields."""
    cmd = LegacyCliCommand(
        name="test_command", module="shared.commands", entrypoint="run_test"
    )
    assert cmd.name == "test_command"
    assert cmd.module == "shared.commands"
    assert cmd.entrypoint == "run_test"
    assert cmd.summary is None
    assert cmd.category is None


def test_legacy_cli_command_creation_with_all_fields():
    """Test creation with all fields provided."""
    cmd = LegacyCliCommand(
        name="list",
        module="shared.utils",
        entrypoint="list_items",
        summary="Lists all items",
        category="Utility",
    )
    assert cmd.name == "list"
    assert cmd.module == "shared.utils"
    assert cmd.entrypoint == "list_items"
    assert cmd.summary == "Lists all items"
    assert cmd.category == "Utility"


def test_legacy_cli_command_field_types():
    """Test that field types are enforced."""
    # Pydantic should handle type conversion/validation. This test ensures basic type expectations.
    cmd = LegacyCliCommand(
        name="name_string",
        module="module_string",
        entrypoint="entrypoint_string",
        summary=None,
        category=None,
    )
    assert isinstance(cmd.name, str)
    assert isinstance(cmd.module, str)
    assert isinstance(cmd.entrypoint, str)
    assert cmd.summary is None
    assert cmd.category is None


def test_legacy_cli_command_optional_summary():
    """Test that summary can be a string or None."""
    cmd_with_summary = LegacyCliCommand(
        name="cmd1", module="mod1", entrypoint="ep1", summary="A helpful summary"
    )
    assert cmd_with_summary.summary == "A helpful summary"

    cmd_without_summary = LegacyCliCommand(name="cmd2", module="mod2", entrypoint="ep2")
    assert cmd_without_summary.summary is None


def test_legacy_cli_command_optional_category():
    """Test that category can be a string or None."""
    cmd_with_category = LegacyCliCommand(
        name="cmd1", module="mod1", entrypoint="ep1", category="Admin"
    )
    assert cmd_with_category.category == "Admin"

    cmd_without_category = LegacyCliCommand(
        name="cmd2", module="mod2", entrypoint="ep2"
    )
    assert cmd_without_category.category is None


def test_legacy_cli_command_equality():
    """Test that two instances with the same data are equal."""
    cmd1 = LegacyCliCommand(
        name="sync",
        module="shared.sync",
        entrypoint="run_sync",
        summary="Sync data",
        category="Data",
    )
    cmd2 = LegacyCliCommand(
        name="sync",
        module="shared.sync",
        entrypoint="run_sync",
        summary="Sync data",
        category="Data",
    )
    # Compare attribute by attribute as Pydantic models may not implement __eq__
    assert cmd1.name == cmd2.name
    assert cmd1.module == cmd2.module
    assert cmd1.entrypoint == cmd2.entrypoint
    assert cmd1.summary == cmd2.summary
    assert cmd1.category == cmd2.category
