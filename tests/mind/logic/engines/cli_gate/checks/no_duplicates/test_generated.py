from __future__ import annotations

from typing import Any

from mind.logic.engines.cli_gate.checks.no_duplicates import NoDuplicatesCheck


# ID: 6dc6ec8d-4c65-4d27-932f-c3cd412b983b
def test_NoDuplicatesCheck_verify() -> None:
    check = NoDuplicatesCheck()
    commands: list[dict[str, Any]] = [
        {
            "name": "build",
            "file_path": "a.py",
            "entrypoint": "cli.a",
        },
        {
            "name": "build",
            "file_path": "b.py",
            "entrypoint": "cli.b",
        },
        {
            "name": "test",
            "file_path": "c.py",
            "entrypoint": "cli.c",
        },
    ]

    findings = check.verify(commands, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.no_duplicates"
    assert "build" in finding.message
    assert finding.file_path == "a.py"
    assert finding.context["command_name"] == "build"
    assert finding.context["registration_count"] == 2
    assert finding.context["entrypoints"] == ["cli.a", "cli.b"]
