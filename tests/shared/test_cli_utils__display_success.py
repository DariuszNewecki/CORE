"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: display_success
- Status: 1 tests passed, some failed
- Passing tests: test_display_success_does_not_print_to_stderr
- Generated: 2026-01-11 10:40:44
"""

from shared.cli_utils import display_success


def test_display_success_does_not_print_to_stderr(capsys):
    """Test that no output is sent to stderr."""
    display_success("Test")
    captured = capsys.readouterr()
    assert captured.err == ""
