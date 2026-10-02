# tests/will/agents/test_test_gen_cognitive_delegate.py
"""
TestGenCognitiveDelegate failure propagation.

GenerationFailedError.violations (the last attempt's acceptance evidence,
including pytest output) must survive the delegate boundary as
CognitiveStepError.details — not be reduced to a count in a log line.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.protocols.cognitive_flow_delegate import CognitiveStepError
from will.agents import test_gen_cognitive_delegate as mod
from will.agents.prompt_model_iterative_agent import GenerationFailedError


def _make_delegate(repo_root, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        mod, "source_to_test_path", lambda _src: "tests/x/test_generated.py"
    )
    monkeypatch.setattr("body.atomic.executor.ActionExecutor", MagicMock())
    (repo_root / "src").mkdir()
    (repo_root / "src" / "x.py").write_text("def f():\n    return 1\n")

    core_context = MagicMock()
    core_context.git_service.repo_path = repo_root
    core_context.cognitive_service = AsyncMock()
    return mod.TestGenCognitiveDelegate(core_context)


# ID: c5dcf5d8-f583-4aef-8f77-e1cb191de0c0
async def test_generation_failure_carries_violations_as_details(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    delegate = _make_delegate(tmp_path, monkeypatch)
    delegate._agent.generate = AsyncMock(
        side_effect=GenerationFailedError(
            step_ref="generate.test_snippet",
            attempts=5,
            violations=["1 error in 1.47s\n\nE   ImportError: cannot import name 'g'"],
            reason="acceptance_rejected",
        )
    )

    with pytest.raises(CognitiveStepError) as exc_info:
        await delegate.execute_cognitive_step(
            "generate.test_snippet",
            {"source_file": "src/x.py", "symbol_name": "f"},
        )

    assert exc_info.value.reason == "acceptance_rejected"
    assert exc_info.value.details == [
        "1 error in 1.47s\n\nE   ImportError: cannot import name 'g'"
    ]


# ID: 64625de9-7073-45ed-9730-20c7cacebc4d
async def test_unknown_step_ref_raises_without_details(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    delegate = _make_delegate(tmp_path, monkeypatch)

    with pytest.raises(CognitiveStepError) as exc_info:
        await delegate.execute_cognitive_step("unknown.step", {})

    assert exc_info.value.step_ref == "unknown.step"
    assert exc_info.value.details == []
