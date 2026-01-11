"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_utils.py
- Symbol: confirm_action
- Status: verified_in_sandbox
- Generated: 2026-01-11 10:39:05
"""

from shared.cli_utils import confirm_action


# The function 'confirm_action' is a regular 'def', not 'async def'.
# Therefore, use regular synchronous test functions.


def test_confirm_action_confirmed_true(monkeypatch):
    """Simulate user input 'y' to confirm."""
    from rich.prompt import Confirm

    monkeypatch.setattr(Confirm, "ask", lambda prompt: True)
    result = confirm_action("Delete everything?")
    assert result


def test_confirm_action_not_confirmed_false(monkeypatch):
    """Simulate user input 'n' to not confirm."""
    from rich.prompt import Confirm

    monkeypatch.setattr(Confirm, "ask", lambda prompt: False)
    result = confirm_action("Delete everything?")
    assert not result


def test_confirm_action_default_abort_message_on_abort(monkeypatch, capsys):
    """When not confirmed, default abort message should be printed."""
    from rich.prompt import Confirm

    monkeypatch.setattr(Confirm, "ask", lambda prompt: False)

    # Capture rich console output via capsys
    result = confirm_action("Proceed?")
    captured = capsys.readouterr()
    # The abort message is printed via console.print with [yellow] tags
    # capsys will capture the ANSI sequences. We check the raw output.
    assert not result
    # The abort message "Aborted." should appear in the output
    assert "Aborted." in captured.out


def test_confirm_action_custom_abort_message_on_abort(monkeypatch, capsys):
    """When not confirmed, custom abort message should be printed."""
    from rich.prompt import Confirm

    monkeypatch.setattr(Confirm, "ask", lambda prompt: False)
    result = confirm_action("Proceed?", abort_message="Operation cancelled.")
    captured = capsys.readouterr()
    assert not result
    assert "Operation cancelled." in captured.out


def test_confirm_action_no_abort_message_on_confirmation(monkeypatch, capsys):
    """When confirmed, abort message should NOT be printed."""
    from rich.prompt import Confirm

    monkeypatch.setattr(Confirm, "ask", lambda prompt: True)
    result = confirm_action("Proceed?", abort_message="Should not see this.")
    captured = capsys.readouterr()
    assert result
    assert "Should not see this." not in captured.out


def test_confirm_action_prompt_message_passed_correctly(monkeypatch):
    """The message parameter should be passed to Confirm.ask."""
    captured_prompt = []
    from rich.prompt import Confirm

    def mock_ask(prompt):
        captured_prompt.append(prompt)
        return True

    monkeypatch.setattr(Confirm, "ask", mock_ask)
    test_message = "Delete file /path/to/important.txt?"
    result = confirm_action(test_message)
    assert captured_prompt[0] == test_message
    assert result
