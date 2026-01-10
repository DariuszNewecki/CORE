"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: confirm_action
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:04:09
"""

import pytest
from shared.cli_utils import confirm_action

# The function returns a boolean value indicating user confirmation

# Since confirm_action is NOT async (doesn't start with 'async def'),
# we use regular synchronous test functions

def test_confirm_action_default_abort_message(monkeypatch):
    """Test confirm_action with default abort_message parameter."""
    # Mock the Confirm.ask to return False
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda x: False)

    result = confirm_action("Proceed with deletion?")

    assert result == False

def test_confirm_action_custom_abort_message(monkeypatch):
    """Test confirm_action with custom abort_message parameter."""
    # Mock the Confirm.ask to return False
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda x: False)

    result = confirm_action("Delete all files?", abort_message="Operation cancelled.")

    assert result == False

def test_confirm_action_confirmed_true(monkeypatch):
    """Test confirm_action when user confirms the action."""
    # Mock the Confirm.ask to return True
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda x: True)

    result = confirm_action("Install package?")

    assert result == True

def test_confirm_action_message_passed_to_prompt(monkeypatch):
    """Test that the message parameter is correctly passed to the prompt."""
    captured_message = None

    def mock_ask(message):
        nonlocal captured_message
        captured_message = message
        return True

    monkeypatch.setattr('shared.cli_utils.Confirm.ask', mock_ask)

    test_message = "Are you sure you want to continue?"
    confirm_action(test_message)

    assert captured_message == test_message

def test_confirm_action_with_empty_message(monkeypatch):
    """Test confirm_action with an empty message string."""
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda x: False)

    result = confirm_action("")

    assert result == False

def test_confirm_action_with_special_characters_message(monkeypatch):
    """Test confirm_action with message containing special characters."""
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda x: True)

    message = "Delete file: important_data.txt? (Yes/No)"
    result = confirm_action(message)

    assert result == True
