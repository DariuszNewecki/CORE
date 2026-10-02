from __future__ import annotations

from unittest.mock import MagicMock

from mind.logic.engines.cli_gate.checks.help_required import (
    _DEFAULT_FINDING_SEVERITY,
    HelpRequiredCheck,
)


# ID: a088476e-03a0-4431-93df-c8bedfc83920
def test_help_required_check_verify() -> None:
    check = MagicMock(spec=HelpRequiredCheck)
    commands = [
        {"name": "cmd_with_summary", "summary": "A helpful summary"},
        {"name": "cmd_without_summary", "summary": ""},
    ]
    findings = HelpRequiredCheck.verify(check, commands, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.help_required"
    assert finding.severity == _DEFAULT_FINDING_SEVERITY
    assert "cmd_without_summary" in finding.message
    assert finding.context == {"command_name": "cmd_without_summary"}




# ID: b2a94a0f-d1aa-402a-bdfa-5fe1e26619a5
def test_HelpRequiredCheck():
    check = HelpRequiredCheck()

    commands = [
        {"name": "documented", "summary": "Has a summary", "file_path": "a.py"},
        {"name": "undocumented", "summary": "", "file_path": "b.py"},
        {"name": "missing", "file_path": "c.py"},
    ]

    findings = check.verify(commands, {})

    assert len(findings) == 2
    for finding in findings:
        assert finding.check_id == "cli_gate.help_required"

    first, second = findings
    assert first.context == {"command_name": "undocumented"}
    assert first.file_path == "b.py"
    assert "undocumented" in first.message

    assert second.context == {"command_name": "missing"}
    assert second.file_path == "c.py"
    assert "missing" in second.message
