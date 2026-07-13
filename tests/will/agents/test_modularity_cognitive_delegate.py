# tests/will/agents/test_modularity_cognitive_delegate.py
"""Tests for ModularityCognitiveDelegate (ADR-140 D6, #769).

No real LLM call — cognitive_service and PromptModel are mocked. Covers
error paths (unknown step, missing file, no violations, plan rejection)
and the happy path (accepted plan threads resolved_file_path + plan_raw).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.protocols.cognitive_flow_delegate import CognitiveStepError
from will.agents.modularity_cognitive_delegate import ModularityCognitiveDelegate


def _make_delegate(repo_root) -> ModularityCognitiveDelegate:
    core_context = MagicMock()
    core_context.git_service.repo_path = repo_root
    core_context.cognitive_service = AsyncMock()
    return ModularityCognitiveDelegate(core_context)


async def test_execute_cognitive_step_unknown_step_ref_raises() -> None:
    delegate = _make_delegate(repo_root=None)
    with pytest.raises(CognitiveStepError) as exc_info:
        await delegate.execute_cognitive_step("unknown.step", {})
    assert exc_info.value.step_ref == "unknown.step"


async def test_analyze_missing_explicit_file_path_raises(tmp_path) -> None:
    delegate = _make_delegate(tmp_path)
    with pytest.raises(CognitiveStepError) as exc_info:
        await delegate.execute_cognitive_step(
            "analyze.modularity_seam", {"file_path": "src/does/not/exist.py"}
        )
    assert "File not found" in exc_info.value.reason


async def test_analyze_no_file_path_and_no_violations_raises(tmp_path) -> None:
    """No caller-supplied file_path and nothing in src/ exceeds the
    line-count threshold -> no_violations_found."""
    (tmp_path / "src").mkdir()
    delegate = _make_delegate(tmp_path)
    with pytest.raises(CognitiveStepError) as exc_info:
        await delegate.execute_cognitive_step("analyze.modularity_seam", {})
    assert exc_info.value.reason == "no_violations_found"


async def test_analyze_low_confidence_plan_raises(tmp_path) -> None:
    """A syntactically valid but low-confidence plan is rejected."""
    src_dir = tmp_path / "src" / "body"
    src_dir.mkdir(parents=True)
    target = src_dir / "big_module.py"
    target.write_text(
        "def foo():\n    pass\n\n\ndef bar():\n    pass\n", encoding="utf-8"
    )

    plan_raw = json.dumps(
        {
            "source_file": "src/body/big_module.py",
            "new_package_name": "big_module",
            "confidence": 0.1,
            "modules": [
                {"module_name": "a", "symbols": ["foo"], "rationale": "x"},
                {"module_name": "b", "symbols": ["bar"], "rationale": "y"},
            ],
        }
    )

    delegate = _make_delegate(tmp_path)
    mock_model = MagicMock()
    mock_model.manifest.role = "architect"
    mock_model.invoke = AsyncMock(return_value=plan_raw)

    with patch(
        "shared.models.prompt_model.PromptModel.load", return_value=mock_model
    ):
        with pytest.raises(CognitiveStepError) as exc_info:
            await delegate.execute_cognitive_step(
                "analyze.modularity_seam", {"file_path": "src/body/big_module.py"}
            )
    assert "low_confidence" in exc_info.value.reason


async def test_analyze_accepted_plan_returns_resolved_path_and_plan_raw(
    tmp_path,
) -> None:
    """A syntactically valid, high-confidence plan referencing only
    locally-defined symbols is accepted and threaded downstream."""
    src_dir = tmp_path / "src" / "body"
    src_dir.mkdir(parents=True)
    target = src_dir / "big_module.py"
    target.write_text(
        "def foo():\n    pass\n\n\ndef bar():\n    pass\n", encoding="utf-8"
    )

    plan_raw = json.dumps(
        {
            "source_file": "src/body/big_module.py",
            "new_package_name": "big_module",
            "confidence": 0.9,
            "modules": [
                {"module_name": "a", "symbols": ["foo"], "rationale": "x"},
                {"module_name": "b", "symbols": ["bar"], "rationale": "y"},
            ],
        }
    )

    delegate = _make_delegate(tmp_path)
    mock_model = MagicMock()
    mock_model.manifest.role = "architect"
    mock_model.invoke = AsyncMock(return_value=plan_raw)

    with patch(
        "shared.models.prompt_model.PromptModel.load", return_value=mock_model
    ):
        result = await delegate.execute_cognitive_step(
            "analyze.modularity_seam", {"file_path": "src/body/big_module.py"}
        )

    assert result["resolved_file_path"] == "src/body/big_module.py"
    assert result["plan_raw"] == plan_raw
