# src/features/self_healing/test_context/formatter.py

"""Provides functionality for the formatter module."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .models import ModuleContext


# ID: 02560995-d66d-493d-8896-138a623a8304
def format_to_prompt(ctx: ModuleContext) -> str:
    """Convert context to formatted string for LLM prompt."""
    lines = [
        "# MODULE CONTEXT",
        f"\n## Module: {ctx.module_path}",
        f"Import as: `{ctx.import_path}`",
    ]
    if ctx.module_docstring:
        lines.extend(["\n## Purpose", ctx.module_docstring])

    lines.extend(
        ["\n## Coverage Status", f"Current Coverage: {ctx.current_coverage:.1f}%"]
    )
    if ctx.uncovered_functions:
        lines.append(f"Uncovered Functions ({len(ctx.uncovered_functions)}):")
        for func in ctx.uncovered_functions[:10]:
            lines.append(f"  - {func}")

    lines.append("\n## Module Structure")
    for cls in ctx.classes:
        lines.append(
            f"  - {cls['name']}: {cls.get('docstring', 'No description')[:80]}"
        )
    for func in ctx.functions:
        lines.append(
            f"  - {func['name']}: {func.get('docstring', 'No description')[:80]}"
        )

    lines.append("\n## Dependencies to Mock")
    if ctx.external_deps:
        lines.append("External dependencies that MUST be mocked:")
        for dep in ctx.external_deps:
            lines.append(f"  - {dep}")

    if ctx.filesystem_usage:
        lines.append(
            "⚠️  This module uses filesystem operations - use tmp_path fixture!"
        )
    if ctx.database_usage:
        lines.append("⚠️  This module uses database - mock get_session()!")
    if ctx.network_usage:
        lines.append("⚠️  This module uses network - mock httpx requests!")

    if ctx.similar_test_files:
        lines.append("\n## Example Test Patterns from Similar Modules")
        for ex in ctx.similar_test_files[:2]:
            lines.extend(
                [f"\n### Example from {ex['file']}", "```python", ex["snippet"], "```"]
            )

    return "\n".join(lines)
