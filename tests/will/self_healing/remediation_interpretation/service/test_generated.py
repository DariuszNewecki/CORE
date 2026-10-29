from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.service import (
    RemediationInterpretationService,
)


# ID: 097db9d1-c8bf-4e6c-96e7-bcb12763db17
def test_RemediationInterpretationService_build_reasoning_brief_dict() -> None:
    service = RemediationInterpretationService()

    expected_dict = {"brief": "value", "nested": {"k": 1}}
    mock_brief = MagicMock()
    mock_brief.to_dict.return_value = expected_dict

    service.build_reasoning_brief = MagicMock(return_value=mock_brief)

    file_path = "src/example.py"
    source_code = "def foo():\n    return 1\n"
    findings = [{"code": "E001", "message": "issue"}]

    result = service.build_reasoning_brief_dict(
        file_path=file_path,
        source_code=source_code,
        findings=findings,
    )

    service.build_reasoning_brief.assert_called_once_with(
        file_path=file_path,
        source_code=source_code,
        findings=findings,
    )
    mock_brief.to_dict.assert_called_once_with()
    assert result == expected_dict
