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
