from __future__ import annotations

from unittest.mock import patch

from rich.table import Table

from cli.commands.check.formatters import print_migration_delta


# ID: 8dd32bab-62f7-4aca-990c-e5fbdde12a5e
def test_print_migration_delta():
    # Arrange
    legacy_executed = {"rule1", "rule2", "rule3", "rule4"}
    v2_rule_ids = {"rule3", "rule4", "rule5", "rule6", "rule7"}

    # Act - mock the console to capture output
    with patch("cli.commands.check.formatters.console") as mock_console:
        print_migration_delta(
            legacy_executed=legacy_executed,
            v2_rule_ids=v2_rule_ids,
        )

    # Assert - verify the console.print was called twice with Table instances
    assert mock_console.print.call_count == 2
    # First call is the main delta table
    delta_table = mock_console.print.call_args_list[0][0][0]
    assert isinstance(delta_table, Table)
    # Check that table has expected title and rows
    assert "Migration Delta" in delta_table.title
    # Verify the row count structure matches (metric, count columns)
    rows = delta_table.columns[0]._cells
    assert rows[0] == "Legacy executed ids (evidence)"
    assert rows[1] == "V2 rule ids (from findings)"
    assert rows[2] == "Overlap"
    assert rows[3] == "Legacy-only"
    assert rows[4] == "V2-only"

    counts = delta_table.columns[1]._cells
    assert counts[0] == str(len(legacy_executed))  # 4
    assert counts[1] == str(len(v2_rule_ids))  # 5
    assert counts[2] == "2"  # overlap: {rule3, rule4}
    assert counts[3] == "2"  # legacy-only: {rule1, rule2}
    assert counts[4] == "3"  # v2-only: {rule5, rule6, rule7}

    # Second call is the samples table
    details_table = mock_console.print.call_args_list[1][0][0]
    assert isinstance(details_table, Table)
    assert "Migration Candidates" in details_table.title
    # Check sample columns
    categories = details_table.columns[0]._cells
    assert categories[0] == "Legacy-only (candidate to migrate)"
    assert categories[1] == "V2-only (new coverage not in legacy evidence)"

    samples = details_table.columns[1]._cells
    # Legacy-only sample should be sorted: "rule1, rule2"
    assert samples[0] == "rule1, rule2"
    # V2-only sample should be sorted: "rule5, rule6, rule7"
    assert samples[1] == "rule5, rule6, rule7"


from cli.commands.check.formatters import print_executed_rules


# ID: 64a20140-0bfd-4267-b190-7fcef7cecf07
def test_print_executed_rules():
    with patch("cli.commands.check.formatters.console") as mock_console:
        executed_rules = {"rule_a", "rule_b"}
        print_executed_rules(executed_rules)
        mock_console.print.assert_any_call("\n[dim]Executed rules:[/dim]")
        mock_console.print.assert_any_call("  [dim]• rule_a[/dim]")
        mock_console.print.assert_any_call("  [dim]• rule_b[/dim]")
        assert mock_console.print.call_count == 3


from cli.commands.check.formatters import print_filtered_audit_summary


# ID: 51bd59d6-e69e-4f1c-97ca-3e02a88292a0
def test_print_filtered_audit_summary():
    """Test the happy path for print_filtered_audit_summary with a passing audit."""
    stats = {
        "total_rules": 10,
        "filtered_rules": 5,
        "executed_rules": 8,
        "failed_rules": 1,
        "total_findings": 3,
    }
    errors = []
    warnings = ["warning1"]

    with patch("cli.commands.check.formatters.console") as mock_console:
        print_filtered_audit_summary(
            passed=True,
            stats=stats,
            errors=errors,
            warnings=warnings,
        )

        # Verify the console.print was called once with a Panel
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args
        assert call_args.args[0].__class__.__name__ == "Panel"
        panel = call_args.args[0]
        assert panel.title == "✅ FILTERED AUDIT PASSED"
        assert panel.style == "bold green"
        assert panel.expand is False


from unittest.mock import MagicMock

from cli.commands.check.formatters import print_audit_summary


# ID: 7ce53205-3627-4910-a135-12108d27d722
def test_print_audit_summary():
    errors = [MagicMock()]
    warnings = [MagicMock(), MagicMock()]
    unassigned_count = 3
    console_mock = MagicMock()
    panel_mock = MagicMock(return_value=MagicMock())

    with (
        patch("cli.commands.check.formatters.console", console_mock),
        patch("cli.commands.check.formatters.Panel", panel_mock),
    ):
        print_audit_summary(
            passed=True,
            errors=errors,
            warnings=warnings,
            unassigned_count=unassigned_count,
            title_prefix="test ",
        )

    console_mock.print.assert_called_once()

    # Verify the panel was created with the correct arguments
    args, kwargs = panel_mock.call_args
    assert len(args) == 1
    assert kwargs["title"] == "✅ test AUDIT PASSED"
    assert kwargs["style"] == "bold green"
    assert kwargs["expand"] is False


from cli.commands.check.formatters import print_hidden_findings_hint


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
