from __future__ import annotations

from mind.logic.engines.cli_gate.checks.resource_first import ResourceFirstCheck


# ID: 247ed00f-8b7c-49e9-b687-00077f83aeb5
def test_resource_first_check_verify():
    check = ResourceFirstCheck()

    commands = [
        {"name": "a.b", "file_path": "one.py"},
        {"name": "a.b.c", "file_path": "two.py"},
        {"name": "too.deep.path.here", "file_path": "three.py"},
    ]

    findings = check.verify(commands, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.resource_first"
    assert finding.file_path == "three.py"
    assert finding.context["command_name"] == "too.deep.path.here"
    assert finding.context["depth"] == 4
    assert finding.context["min_depth"] == 2
    assert finding.context["max_depth"] == 3
