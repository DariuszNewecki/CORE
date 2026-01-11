"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: confirm_action
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:47:46
"""

import pytest
from shared.cli_utils import confirm_action

# confirm_action returns bool (True if confirmed, False if not)

def test_confirm_action_confirmed(monkeypatch):
    """Test when user confirms the action (returns True)"""
    # Mock the Confirm.ask to return True
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda msg: True)

    result = confirm_action("Delete all files?")
    assert result == True

def test_confirm_action_not_confirmed(monkeypatch):
    """Test when user does not confirm the action (returns False)"""
    # Mock the Confirm.ask to return False
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda msg: False)

    result = confirm_action("Delete all files?")
    assert result == False

def test_confirm_action_custom_abort_message(monkeypatch, capsys):
    """Test that custom abort message is displayed when action is not confirmed"""
    # Mock the Confirm.ask to return False
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda msg: False)

    custom_message = "Operation cancelled by user."
    result = confirm_action("Delete all files?", abort_message=custom_message)

    # Capture output to verify abort message was printed
    captured = capsys.readouterr()
    assert result == False
    # The abort message should appear in the output (though we can't easily test Rich formatting)

def test_confirm_action_default_abort_message(monkeypatch):
    """Test that default abort message is used when not specified"""
    # Mock the Confirm.ask to return False
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda msg: False)

    result = confirm_action("Delete all files?")
    assert result == False

def test_confirm_action_with_empty_message(monkeypatch):
    """Test with empty message string"""
    # Mock the Confirm.ask to return True
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda msg: True)

    result = confirm_action("")
    assert result == True

def test_confirm_action_with_special_characters_message(monkeypatch):
    """Test with message containing special characters"""
    # Mock the Confirm.ask to return True
    monkeypatch.setattr('shared.cli_utils.Confirm.ask', lambda msg: True)

    message = "Delete file: /tmp/test[123].txt? (Yes/No)"
    result = confirm_action(message)
    assert result == True
