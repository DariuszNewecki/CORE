from __future__ import annotations

from unittest.mock import MagicMock

from will.agents.code_generation.pattern_validator import PatternValidator


# ID: ead2b020-a390-43b2-b140-a48a19ff9b8c
def test_PatternValidator_get_pattern_requirements():
    intent_guard = MagicMock()
    validator = PatternValidator(intent_guard)

    result = validator.get_pattern_requirements("pure_function")

    assert isinstance(result, str)
    assert "Pattern Requirements: pure_function" in result
    assert "deterministic" in result
    assert intent_guard is validator.intent_guard


from unittest.mock import patch


# ID: 7d7d50c1-3eaf-469c-ae9f-c69dbd2772c8
def test_PatternValidator_infer_pattern_id():
    intent_guard = MagicMock()
    validator = PatternValidator(intent_guard=intent_guard)

    task = MagicMock()
    task.step = "expand the parsing logic for the tokenizer"
    task.params = MagicMock()
    task.params.pattern_id = None
    task.params.file_path = "src/will/core/parsing/tokenizer.py"

    with patch.object(
        PatternValidator, "_classify_function_type", return_value="pure_function"
    ) as mock_classify:
        result = validator.infer_pattern_id(task)

    mock_classify.assert_called_once_with(
        "src/will/core/parsing/tokenizer.py",
        "expand the parsing logic for the tokenizer",
    )
    assert result == "pure_function"





# ID: 41005b44-7a0e-4988-b0b6-c87e5098cecc
def test_PatternValidator():
    intent_guard = MagicMock()
    validator = PatternValidator(intent_guard=intent_guard)

    task = MagicMock()
    task.params.pattern_id = "action_pattern"
    task.params.file_path = "src/will/body/atomic/do_thing.py"
    task.step = "create a thing"

    result = validator.infer_pattern_id(task)

    assert result == "action_pattern"
    assert validator.intent_guard is intent_guard
