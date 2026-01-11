"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/cli/admin_cli.py
- Symbol: register_all_commands
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:16:16
"""

import pytest

from body.cli.admin_cli import register_all_commands


# Detected return type: None (function registers commands but returns nothing)


def test_register_all_commands_adds_all_typers():
    """Test that register_all_commands adds all expected subcommands."""

    # Create a mock Typer instance to track calls
    class MockTyper:
        def __init__(self):
            self.added_typers = []
            self.commands = []

        def add_typer(self, typer_app, name=None):
            self.added_typers.append((typer_app, name))

        def command(self, name=None):
            def decorator(func):
                self.commands.append((name, func))
                return func

            return decorator

    mock_app = MockTyper()

    # Call the function
    register_all_commands(mock_app)

    # Verify all expected typer apps were added
    expected_names = [
        "check",
        "components",
        "coverage",
        "enrich",
        "fix",
        "governance",
        "inspect",
        "manage",
        "mind",
        "run",
        "search",
        "submit",
        "secrets",
        "context",
        "develop",
        "patterns",
        "dev",
        "atomic-actions",
        "autonomy",
        "tools",
        "diagnostics",
        "interactive-test",
    ]

    # Check that we have the right number of added typers
    assert len(mock_app.added_typers) == len(expected_names)

    # Check that all expected names are present
    added_names = [name for _, name in mock_app.added_typers]
    for expected_name in expected_names:
        assert expected_name in added_names

    # Verify the direct command registration
    assert len(mock_app.commands) == 1
    assert mock_app.commands[0][0] == "inspect-patterns"


def test_register_all_commands_returns_none():
    """Test that register_all_commands returns None."""

    class MockTyper:
        def add_typer(self, *args, **kwargs):
            pass

        def command(self, name=None):
            def decorator(func):
                return func

            return decorator

    mock_app = MockTyper()
    result = register_all_commands(mock_app)
    assert result is None


def test_register_all_commands_order_preserved():
    """Test that commands are registered in the expected order."""

    class MockTyper:
        def __init__(self):
            self.registration_order = []

        def add_typer(self, typer_app, name=None):
            self.registration_order.append(("typer", name))

        def command(self, name=None):
            def decorator(func):
                self.registration_order.append(("command", name))
                return func

            return decorator

    mock_app = MockTyper()
    register_all_commands(mock_app)

    # Check first few registrations are in correct order
    assert mock_app.registration_order[0] == ("typer", "check")
    assert mock_app.registration_order[1] == ("typer", "components")
    assert mock_app.registration_order[2] == ("typer", "coverage")

    # Check last registration is the direct command
    assert mock_app.registration_order[-1] == ("command", "inspect-patterns")


def test_register_all_commands_with_real_typer_instance():
    """Test with actual Typer instance to ensure no runtime errors."""
    import typer

    app = typer.Typer()

    # This should not raise any exceptions
    try:
        register_all_commands(app)
        # If we get here, the function executed successfully
        assert True
    except Exception as e:
        pytest.fail(f"register_all_commands raised an exception: {e}")
