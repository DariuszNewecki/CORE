# tests/integration/test_a1_autonomy_loop.py
"""
Integration tests for the A1 Autonomy Loop, ensuring that the system can
autonomously propose, validate, and apply self-healing micro-proposals.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from cli.logic.proposals_micro import propose_and_apply_autonomously
from shared.context import CoreContext


@pytest.mark.asyncio
async def test_fix_docstrings_autonomously(mock_core_env, mocker):
    """
    Verify the full A1 loop for fixing a missing docstring.
    """
    # 1. ARRANGE: Create a file with a function missing a docstring.
    repo_root = mock_core_env
    (repo_root / "src" / "app").mkdir(parents=True, exist_ok=True)
    test_file_path = repo_root / "src" / "app" / "main.py"
    original_code = "def my_function():\n    pass"
    test_file_path.write_text(original_code)

    # 2. ARRANGE: Mock the LLM response for the MicroPlannerAgent
    # This is a more robust approach than mocking the agent class itself.
    mock_plan = [
        {
            "step": "Add missing docstring to my_function in src/app/main.py",
            "action": "autonomy.self_healing.fix_docstrings",
            "params": {"file_path": "src/app/main.py"},
        },
        {
            "step": "Validate the changes.",
            "action": "core.validation.validate_code",
            "params": {"file_path": None},
        },
    ]
    mock_plan_json = json.dumps(mock_plan)

    # Mock the LLM client that the MicroPlannerAgent will use
    mock_llm_client = MagicMock()
    mock_llm_client.make_request_async = AsyncMock(return_value=mock_plan_json)

    # Mock the CognitiveService to return our mock client
    mock_cognitive_service = MagicMock()
    mock_cognitive_service.aget_client_for_role = AsyncMock(
        return_value=mock_llm_client
    )

    # Mock the specific docstring generation AI call to return a predictable docstring
    async def mock_fix_docstrings(dry_run):
        lines = original_code.splitlines()
        lines.insert(1, '    """This is a test docstring."""')
        test_file_path.write_text("\n".join(lines) + "\n")

    mocker.patch(
        "core.actions.healing_actions._async_fix_docstrings",
        new=AsyncMock(side_effect=mock_fix_docstrings),
    )

    # 3. ACT: Run the entire A1 autonomy loop with a high-level goal.
    goal = "Add missing docstrings to src/app/main.py"

    # Create a context with our mocked CognitiveService
    context = CoreContext(
        git_service=MagicMock(),
        cognitive_service=mock_cognitive_service,
        knowledge_service=MagicMock(),
        qdrant_service=MagicMock(),
        auditor_context=MagicMock(),
        file_handler=MagicMock(),
        planner_config=MagicMock(),
    )

    # Mock the file handler to allow writes
    context.planner_config.task_timeout = 30
    context.file_handler.repo_path = repo_root

    await propose_and_apply_autonomously(context=context, goal=goal)

    # 4. ASSERT: Check that the file was modified correctly.
    final_code = test_file_path.read_text()
    assert '"""This is a test docstring."""' in final_code
    assert "def my_function():" in final_code
