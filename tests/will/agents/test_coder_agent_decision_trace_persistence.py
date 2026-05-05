"""Persistence: generate_or_repair must save the decision trace on every exit.

Pins that DecisionTracer.save_trace is awaited from generate_or_repair's
finally block. Without the await, the trace built up by upstream
record() calls never reaches disk or the database, and post-mortem
debugging of an autonomous run is impossible.

Exercises the no-pain-signal branch (normal-return path); the finally
covers the repair path and exception path identically.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.coder_agent import CoderAgent


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ID: 7c2a9e84-3f5b-4d18-a062-9b1f4e7c3a25
async def test_generate_or_repair_awaits_save_trace_in_finally() -> None:
    coder = CoderAgent(
        cognitive_service=MagicMock(name="CognitiveProtocol"),
        executor=MagicMock(name="ActionExecutorProtocol"),
        prompt_pipeline=MagicMock(name="PromptPipeline"),
        auditor_context=MagicMock(name="AuditorContext"),
        repo_root=_REPO_ROOT,
    )

    fake_code = "def foo() -> int:\n    return 1\n"

    coder.tracer.save_trace = AsyncMock(return_value=None)
    coder.code_generator = MagicMock()
    coder.code_generator.generate_code = AsyncMock(return_value=fake_code)
    coder.pattern_validator = MagicMock()
    coder.pattern_validator.infer_pattern_id.return_value = "default"
    coder.pattern_validator.get_pattern_requirements.return_value = {}

    task = MagicMock()
    task.step = "implement foo"

    with patch(
        "will.agents.coder_agent.handle_code_generation_result",
        new=AsyncMock(return_value=fake_code),
    ):
        result = await coder.generate_or_repair(task=task, goal="make foo")

    assert result == fake_code
    coder.tracer.save_trace.assert_awaited_once()
