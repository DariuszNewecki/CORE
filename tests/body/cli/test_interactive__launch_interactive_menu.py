"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/cli/interactive.py
- Symbol: launch_interactive_menu
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:15:46
"""

import pytest
from body.cli.interactive import launch_interactive_menu

# The target function 'launch_interactive_menu' is a regular 'def' (not async).
# It has an infinite loop and calls other functions, but does not return a value.
# It will run until the user inputs 'q' to break the loop.

def test_launch_interactive_menu_calls_show_development_menu_on_1(monkeypatch):
    """Test that entering '1' triggers the development menu."""
    call_log = []
    def mock_show_development_menu():
        call_log.append("show_development_menu")

    monkeypatch.setattr('body.cli.interactive.show_development_menu', mock_show_development_menu)
    # Simulate user entering '1' then 'q' to exit the loop
    inputs = iter(['1', 'q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    # Prevent console.clear from printing during test
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == ["show_development_menu"]

def test_launch_interactive_menu_calls_show_governance_menu_on_2(monkeypatch):
    """Test that entering '2' triggers the governance menu."""
    call_log = []
    def mock_show_governance_menu():
        call_log.append("show_governance_menu")

    monkeypatch.setattr('body.cli.interactive.show_governance_menu', mock_show_governance_menu)
    inputs = iter(['2', 'q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == ["show_governance_menu"]

def test_launch_interactive_menu_calls_show_system_menu_on_3(monkeypatch):
    """Test that entering '3' triggers the system menu."""
    call_log = []
    def mock_show_system_menu():
        call_log.append("show_system_menu")

    monkeypatch.setattr('body.cli.interactive.show_system_menu', mock_show_system_menu)
    inputs = iter(['3', 'q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == ["show_system_menu"]

def test_launch_interactive_menu_calls_show_project_lifecycle_menu_on_4(monkeypatch):
    """Test that entering '4' triggers the project lifecycle menu."""
    call_log = []
    def mock_show_project_lifecycle_menu():
        call_log.append("show_project_lifecycle_menu")

    monkeypatch.setattr('body.cli.interactive.show_project_lifecycle_menu', mock_show_project_lifecycle_menu)
    inputs = iter(['4', 'q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == ["show_project_lifecycle_menu"]

def test_launch_interactive_menu_exits_on_lowercase_q(monkeypatch):
    """Test that entering 'q' (lowercase) breaks the loop and exits."""
    call_log = []
    def mock_show_development_menu():
        call_log.append("should_not_be_called")

    monkeypatch.setattr('body.cli.interactive.show_development_menu', mock_show_development_menu)
    inputs = iter(['q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == []

def test_launch_interactive_menu_exits_on_uppercase_q(monkeypatch):
    """Test that entering 'Q' (uppercase) breaks the loop and exits."""
    call_log = []
    def mock_show_development_menu():
        call_log.append("should_not_be_called")

    monkeypatch.setattr('body.cli.interactive.show_development_menu', mock_show_development_menu)
    inputs = iter(['Q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == []

def test_launch_interactive_menu_ignores_invalid_input_then_exits(monkeypatch):
    """Test that an invalid input is ignored, loop continues, and 'q' still exits."""
    call_log = []
    def mock_show_development_menu():
        call_log.append("show_development_menu")

    monkeypatch.setattr('body.cli.interactive.show_development_menu', mock_show_development_menu)
    # Simulate invalid input 'x', then valid '1', then 'q'
    inputs = iter(['x', '1', 'q'])
    monkeypatch.setattr('body.cli.interactive.console.input', lambda _: next(inputs))
    monkeypatch.setattr('body.cli.interactive.console.clear', lambda: None)

    launch_interactive_menu()
    assert call_log == ["show_development_menu"]
