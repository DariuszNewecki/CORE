from __future__ import annotations

from unittest.mock import MagicMock

from will.agents.code_generation.prompt_builders import build_standard_prompt


# ID: 9e6ea7cd-13e8-4738-8b28-0eac3640d930
def test_build_standard_prompt():
    task = MagicMock()
    task.step = 3

    result = build_standard_prompt(
        task=task,
        goal="Generate a greeting function",
        context_str="No prior context",
        pattern_requirements="Follow functional patterns",
    )

    assert isinstance(result, str)
    assert "# Task: Generate a greeting function" in result
    assert "Step: 3" in result
    assert "Follow functional patterns" in result
    assert "## Context" in result
    assert "No prior context" in result
    assert "## Requirements" in result
    assert "1. Return ONLY valid Python code" in result
    assert "2. Include all necessary imports" in result
    assert "3. Include docstrings" in result
