"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/cli/interactive.py
- Symbol: show_development_menu
- Status: 3 tests passed, some failed
- Passing tests: test_show_development_menu_is_synchronous, test_show_development_menu_is_callable, test_show_development_menu_has_correct_docstring
- Generated: 2026-01-11 03:13:47
"""

from body.cli.interactive import show_development_menu


def test_show_development_menu_is_synchronous():
    """Verify the function is synchronous (not async)."""
    assert (
        not hasattr(show_development_menu, "__code__")
        or "await" not in show_development_menu.__code__.co_names
    )


def test_show_development_menu_is_callable():
    """Verify the function exists and is callable."""
    assert callable(show_development_menu)


def test_show_development_menu_has_correct_docstring():
    """Verify the function has the expected docstring."""
    expected_docstring = "Displays the AI Development & Self-Healing submenu."
    assert show_development_menu.__doc__ == expected_docstring
