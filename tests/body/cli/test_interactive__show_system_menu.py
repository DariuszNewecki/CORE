"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/cli/interactive.py
- Symbol: show_system_menu
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:14:27
"""

from body.cli.interactive import show_system_menu


# Detected return type: None (function prints to stdout/stderr, no return value).


def test_show_system_menu_is_defined():
    """Test that the function exists and is callable."""
    assert callable(show_system_menu)


def test_show_system_menu_calls_show_menu_with_correct_title(monkeypatch):
    """Test that _show_menu is called with the correct title."""
    captured_args = {}
    captured_kwargs = {}

    def mock_show_menu(*args, **kwargs):
        captured_args["args"] = args
        captured_kwargs.update(kwargs)

    monkeypatch.setattr("body.cli.interactive._show_menu", mock_show_menu)
    show_system_menu()
    assert "title" in captured_kwargs
    assert captured_kwargs["title"] == "System Health & CI"


def test_show_system_menu_calls_show_menu_with_correct_options(monkeypatch):
    """Test that _show_menu is called with the correct options dict."""
    captured_kwargs = {}

    def mock_show_menu(*args, **kwargs):
        captured_kwargs.update(kwargs)

    monkeypatch.setattr("body.cli.interactive._show_menu", mock_show_menu)
    show_system_menu()
    assert "options" in captured_kwargs
    expected_options = {
        "1": "Run Full Check (lint, test, audit)",
        "2": "Run Only Tests",
        "3": "Format All Code",
    }
    assert captured_kwargs["options"] == expected_options


def test_show_system_menu_calls_show_menu_with_actions_dict(monkeypatch):
    """Test that _show_menu is called with an actions dict containing callables."""
    captured_kwargs = {}

    def mock_show_menu(*args, **kwargs):
        captured_kwargs.update(kwargs)

    monkeypatch.setattr("body.cli.interactive._show_menu", mock_show_menu)
    show_system_menu()
    assert "actions" in captured_kwargs
    actions = captured_kwargs["actions"]
    assert isinstance(actions, dict)
    assert len(actions) == 3
    assert all(key in actions for key in ("1", "2", "3"))
    # Check that each action is a callable lambda
    assert callable(actions["1"])
    assert callable(actions["2"])
    assert callable(actions["3"])
