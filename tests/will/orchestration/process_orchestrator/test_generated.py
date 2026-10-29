from __future__ import annotations

from unittest.mock import MagicMock

from will.orchestration.process_orchestrator import evaluate_workflow_result


# ID: e88094d1-c6cb-4471-b6ff-2c2404795273
def test_evaluate_workflow_result():
    result = MagicMock()
    result.ok = True
    result.confidence = 0.9
    result.data = {"file_type": "python", "complexity": 3}

    success, reason = evaluate_workflow_result(
        result,
        expected_keys=["file_type", "complexity"],
        min_confidence=0.7,
    )

    assert success is True
    assert reason == "Success"
