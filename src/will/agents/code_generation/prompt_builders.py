# src/will/agents/code_generation/prompt_builders.py
# ID: f5d94444-5380-4579-95c9-c8a3e6c08ea9

"""
Prompt building utilities for code generation.

Three modes:
- Semantic mode: Full architectural context
- Enriched mode: ContextPackage with dependencies
- Standard mode: Basic string context
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from will.tools.context.formatter import format_context_to_markdown

from .context_formatters import (
    format_dependencies,
    format_existing_code,
    format_similar_symbols,
)


if TYPE_CHECKING:
    from shared.models import ExecutionTask


# ID: 9f59227a-7966-47ca-8902-16689d29179e
def build_semantic_prompt(
    arch_context: Any,
    task: ExecutionTask,
    manual_context: str,
    pattern_requirements: str,
) -> str:
    """
    Build prompt using semantic architectural context.

    Args:
        arch_context: Architectural context from ArchitecturalContextBuilder
        task: Execution task
        manual_context: Additional manual context
        pattern_requirements: Pattern requirements text

    Returns:
        Formatted prompt string
    """
    context_text = format_context_to_markdown(arch_context)

    parts = [
        context_text,
        "",
        pattern_requirements,
        "",
        "## Implementation Task",
        f"Step: {task.step}",
    ]

    if task.params.symbol_name:
        parts.append(f"Symbol: {task.params.symbol_name}")

    parts.extend(
        [
            "",
            "## Additional Context",
            manual_context,
            "",
            "## Output Requirements",
            "1. Return ONLY valid Python code.",
            "2. Include all necessary imports.",
            "3. Include docstrings and type hints.",
            "4. Follow constitutional patterns.",
        ]
    )

    return "\n".join(parts)


# ID: 8d27950e-1bbf-46d8-8640-0b3cc5145d80
def build_enriched_prompt(
    task: ExecutionTask,
    goal: str,
    context_package: dict[str, Any],
    manual_context: str,
    pattern_requirements: str,
) -> str:
    """
    Build prompt using ContextPackage items.

    Args:
        task: Execution task
        goal: High-level goal
        context_package: Context package from ContextService
        manual_context: Additional manual context
        pattern_requirements: Pattern requirements

    Returns:
        Formatted prompt string
    """
    # Extract context items
    items = context_package.get("context", [])

    # Format different context types
    dependencies = format_dependencies(items)
    similar_symbols = format_similar_symbols(items)
    existing_code = format_existing_code(items, task.params.file_path)

    parts = [
        "# Code Generation Task",
        "",
        f"**Goal:** {goal}",
        f"**Step:** {task.step}",
        "",
        "## Pattern Requirements",
        pattern_requirements,
        "",
    ]

    if dependencies:
        parts.extend(
            [
                "## Available Dependencies",
                dependencies,
                "",
            ]
        )

    if similar_symbols:
        parts.extend(
            [
                "## Similar Implementations (for reference)",
                similar_symbols,
                "",
            ]
        )

    if existing_code:
        parts.extend(
            [
                "## Existing Code Context",
                existing_code,
                "",
            ]
        )

    if manual_context:
        parts.extend(
            [
                "## Additional Context",
                manual_context,
                "",
            ]
        )

    parts.extend(
        [
            "## Implementation Requirements",
            "1. Return ONLY valid Python code",
            "2. Include all necessary imports",
            "3. Include docstrings and type hints",
            "4. Follow the specified pattern requirements",
            "5. Use similar implementations as reference (not verbatim)",
            "",
            "## Code to Generate",
        ]
    )

    if task.params.symbol_name:
        parts.append(f"Symbol: `{task.params.symbol_name}`")
    if task.params.file_path:
        parts.append(f"Target file: `{task.params.file_path}`")

    return "\n".join(parts)


# ID: 2a883b52-bd79-4171-87ee-34623cd2f5f5
def build_standard_prompt(
    task: ExecutionTask,
    goal: str,
    context_str: str,
    pattern_requirements: str,
) -> str:
    """
    Build basic prompt with minimal context.

    Args:
        task: Execution task
        goal: High-level goal
        context_str: Context string
        pattern_requirements: Pattern requirements

    Returns:
        Formatted prompt string
    """
    parts = [
        f"# Task: {goal}",
        f"Step: {task.step}",
        "",
        pattern_requirements,
        "",
        "## Context",
        context_str,
        "",
        "## Requirements",
        "1. Return ONLY valid Python code",
        "2. Include all necessary imports",
        "3. Include docstrings",
    ]
    return "\n".join(parts)
