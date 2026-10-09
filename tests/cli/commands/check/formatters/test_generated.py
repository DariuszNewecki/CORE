from __future__ import annotations

from unittest.mock import MagicMock, patch

from cli.commands.check.formatters import (
    print_hidden_findings_hint,
)


# ID: 3b420928-040c-433a-9a86-96904f0318e7
def test_print_hidden_findings_hint():
    all_findings = [MagicMock(), MagicMock(), MagicMock()]
    filtered_findings = [MagicMock()]

    with patch("cli.commands.check.formatters.console") as mock_console:
        # Mock AuditSeverity - use a simple object with comparison operators
        min_severity = MagicMock()
        min_severity.__le__ = lambda self, other: False
        min_severity.__gt__ = lambda self, other: True
        print_hidden_findings_hint(all_findings, filtered_findings, min_severity)
        mock_console.print.assert_called_once()

        # Test hidden count is correct
        call_args = mock_console.print.call_args[0][0]
        assert "2 additional finding(s)" in call_args


from pathlib import Path

from cli.commands.check.formatters import print_verbose_findings


# ID: cf0b5baa-63fd-4486-9cf0-0a982877fb2d
def test_print_verbose_findings():
    """Happy path: prints findings with severity styles and table configuration."""
    finding1 = MagicMock()
    finding1.severity = "high"
    finding1.evidence_class = "standard"
    finding1.check_id = "CHECK-ONE"
    finding1.message = "High severity issue"
    finding1.file_path = Path("/tmp/test.py")
    finding1.line_number = 42
    finding1.context = {}

    finding2 = MagicMock()
    finding2.severity = "info"
    finding2.evidence_class = "custom"
    finding2.check_id = "CHECK-TWO"
    finding2.message = "Info message"
    finding2.file_path = Path("/tmp/other.py")
    finding2.line_number = 10
    finding2.context = {"issue_count": 5}

    mock_table = MagicMock()
    mock_console = MagicMock()

    with (
        patch("cli.commands.check.formatters.console", mock_console),
        patch(
            "cli.commands.check.formatters.Table", return_value=mock_table
        ) as mock_table_class,
    ):
        print_verbose_findings([finding1, finding2])

        mock_table_class.assert_called_once_with(
            title="[bold]Verbose Audit Findings[/bold]",
            show_header=True,
            header_style="bold magenta",
        )
        mock_table.add_column.assert_any_call("Severity", style="cyan")
        mock_table.add_column.assert_any_call("Evidence", style="green")
        mock_table.add_column.assert_any_call("Check ID", style="magenta")
        mock_table.add_column.assert_any_call("Message", style="white", overflow="fold")
        mock_table.add_column.assert_any_call("File:Line", style="yellow")

        assert mock_table.add_row.call_count == 2
        first_row = mock_table.add_row.call_args_list[0].args
        assert first_row[0] == "high"
        assert first_row[1] == "standard"
        assert first_row[2] == "CHECK-ONE"
        assert first_row[3] == "High severity issue"
        assert first_row[4] == "/tmp/test.py:42"

        second_row = mock_table.add_row.call_args_list[1].args
        assert second_row[0] == "info"
        assert second_row[1] == "custom"
        assert second_row[2] == "CHECK-TWO"
        assert second_row[3] == "Info message"
        assert second_row[4] == "/tmp/other.py:10 (x5)"

        mock_console.print.assert_called_once_with(mock_table)
