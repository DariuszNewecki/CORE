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


from types import SimpleNamespace
from unittest.mock import patch

from will.agents.code_generation.prompt_builders import build_enriched_prompt


# ID: 0a752aac-7ee7-4d3d-b7fd-d1520167973a
def test_build_enriched_prompt():
    task = SimpleNamespace(
        step="step-1",
        params=SimpleNamespace(
            file_path="src/example.py",
            symbol_name="my_function",
        ),
    )

    context_package = {
        "context": [
            {"type": "dependency", "content": "import os"},
            {"type": "similar_symbol", "content": "def foo(): pass"},
            {"type": "existing_code", "content": "def bar(): pass"},
        ]
    }

    with (
        patch(
            "will.agents.code_generation.prompt_builders.format_dependencies",
            return_value="DEPENDENCIES",
        ) as mock_deps,
        patch(
            "will.agents.code_generation.prompt_builders.format_similar_symbols",
            return_value="SIMILAR",
        ) as mock_sim,
        patch(
            "will.agents.code_generation.prompt_builders.format_existing_code",
            return_value="EXISTING",
        ) as mock_existing,
    ):
        result = build_enriched_prompt(
            task=task,
            goal="Do the thing",
            context_package=context_package,
            manual_context="MANUAL",
            pattern_requirements="PATTERN",
        )

    assert isinstance(result, str)
    assert "# Code Generation Task" in result
    assert "**Goal:** Do the thing" in result
    assert "**Step:** step-1" in result
    assert "## Pattern Requirements" in result
    assert "PATTERN" in result
    assert "## Available Dependencies" in result
    assert "DEPENDENCIES" in result
    assert "## Similar Implementations (for reference)" in result
    assert "SIMILAR" in result
    assert "## Existing Code Context" in result
    assert "EXISTING" in result
    assert "## Additional Context" in result
    assert "MANUAL" in result
    assert "## Implementation Requirements" in result
    assert "## Code to Generate" in result
    assert "Symbol: `my_function`" in result
    assert "Target file: `src/example.py`" in result

    mock_deps.assert_called_once_with(context_package["context"])
    mock_sim.assert_called_once_with(context_package["context"])
    mock_existing.assert_called_once_with(context_package["context"], "src/example.py")
