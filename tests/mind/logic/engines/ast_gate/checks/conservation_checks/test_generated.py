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


from unittest.mock import MagicMock


# ID: 74ca2a57-b85f-4191-8672-3dd9f27a15ec
def test_ConservationChecks_check_logic_conservation():
    original_source = (
        "def public_function():\n    return 1\n\ndef another_public():\n    return 2\n"
    )
    current_source = (
        "def public_function():\n    return 1\n\ndef another_public():\n    return 2\n"
    )

    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = original_source
    mock_path.name = "sample.py"

    violations = ConservationChecks.check_logic_conservation(
        mock_path, current_source, {}
    )

    assert violations == []
    mock_path.read_text.assert_called_once_with(encoding="utf-8")
