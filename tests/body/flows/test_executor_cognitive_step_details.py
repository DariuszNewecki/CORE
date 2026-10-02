# tests/body/flows/test_executor_cognitive_step_details.py
"""
FlowExecutor records CognitiveStepError.details on the failed StepResult.

Before this, a cognitive step failure kept only the reason label
("acceptance_rejected") — the evidence behind it (pytest output of the last
attempt) was dropped, so failed test-gen proposals could not be triaged.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from body.flows.executor import FlowExecutor
from body.flows.registry import FlowStep, StepKind
from shared.protocols.cognitive_flow_delegate import CognitiveStepError


class _RaisingDelegate:
    def __init__(self, exc: CognitiveStepError) -> None:
        self._exc = exc

    async def execute_cognitive_step(self, step_ref, params):
        raise self._exc


async def _run(exc: CognitiveStepError):
    executor = FlowExecutor(
        core_context=MagicMock(), cognitive_delegate=_RaisingDelegate(exc)
    )
    step = FlowStep(ref_id="generate.test_snippet", kind=StepKind.COGNITIVE)
    return await executor._execute_cognitive_step(step, {}, time.time())


# ID: 2dd50831-e55d-4344-8748-593e83d1c3a1
async def test_cognitive_step_failure_records_details() -> None:
    exc = CognitiveStepError(
        step_ref="generate.test_snippet",
        reason="acceptance_rejected",
        details=["E   ModuleNotFoundError: No module named 'x'"],
    )

    result = await _run(exc)

    assert not result.ok
    assert result.data["error"] == "acceptance_rejected"
    assert result.data["details"] == ["E   ModuleNotFoundError: No module named 'x'"]


# ID: 90c5cc1d-89c1-4b22-bfbc-133fb1ddb504
async def test_cognitive_step_failure_without_details_omits_key() -> None:
    exc = CognitiveStepError(step_ref="generate.test_snippet", reason="no_code_fence")

    result = await _run(exc)

    assert not result.ok
    assert result.data == {
        "error": "no_code_fence",
        "step_ref": "generate.test_snippet",
    }


# ID: 428a453d-5581-4313-8f5e-49d0620e8d68
def test_cognitive_step_error_details_default_empty() -> None:
    exc = CognitiveStepError(step_ref="s", reason="r")

    assert exc.details == []
    assert str(exc) == "Cognitive step 's' failed: r"
