from __future__ import annotations

from mind.logic.engines.cli_gate.checks.standard_verbs import StandardVerbsCheck


# ID: 51104b95-cbe9-4026-a1f0-38cb4e583b49
def test_StandardVerbsCheck_verify():
    check = StandardVerbsCheck()
    commands = [
        {"name": "repo.list", "file_path": "f1.py"},
        {"name": "repo.delete", "file_path": "f2.py"},
    ]
    params = {"allowed_verbs": ["list"]}

    findings = check.verify(commands, params)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.standard_verbs"
    assert finding.file_path == "f2.py"
    assert finding.context["command_name"] == "repo.delete"
    assert finding.context["action"] == "delete"


# ID: b08dd75b-5931-4ead-b1f9-a7b06d5063c0
def test_StandardVerbsCheck():
    check = StandardVerbsCheck()
    commands = [
        {"name": "resource.list", "file_path": "a.py"},
        {"name": "resource.delete", "file_path": "b.py"},
    ]
    params = {"allowed_verbs": ["list"]}

    findings = check.verify(commands, params)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.standard_verbs"
    assert "resource.delete" in finding.message
    assert "delete" in finding.message
    assert finding.file_path == "b.py"
    assert finding.context == {"command_name": "resource.delete", "action": "delete"}
