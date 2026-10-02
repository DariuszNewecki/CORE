from __future__ import annotations

from pathlib import Path

from mind.logic.engines.ast_gate.checks.conservation_checks import ConservationChecks


# ID: 98e0dd78-c963-4ef4-b9da-a6f0abac80af
def test_ConservationChecks(tmp_path: Path) -> None:
    original_source = "def foo():\n    return 1\n"
    current_source = "def foo():\n    return 2\n"

    file_path = tmp_path / "example.py"
    file_path.write_text(original_source, encoding="utf-8")

    violations = ConservationChecks.check_logic_conservation(
        file_path=file_path,
        current_source=current_source,
        params={},
    )

    assert violations == []
    assert isinstance(violations, list)
