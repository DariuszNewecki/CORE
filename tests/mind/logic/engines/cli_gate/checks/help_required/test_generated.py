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
