from __future__ import annotations

from unittest.mock import MagicMock, patch

from body.governance.intent_pattern_validators import PatternValidators


# ID: 53a994f0-34b1-452c-9db8-92ba6138c5cd
def test_PatternValidators_validate() -> None:
    sentinel_violations = [MagicMock(name="violation")]

    with patch.object(
        PatternValidators,
        "validate_test_file_pattern",
        return_value=sentinel_violations,
    ) as mock_validator:
        result = PatternValidators.validate(
            "some code",
            "test_file",
            "some_component",
            "path/to/target",
        )

    mock_validator.assert_called_once_with("some code", "path/to/target")
    assert result is sentinel_violations
