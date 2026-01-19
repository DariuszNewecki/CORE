# src/features/self_healing/test_context/models.py

"""Provides functionality for the models module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
# ID: 8dde3ec5-ce2c-4486-b6d7-7751ceaabfd0
class ModuleContext:
    """Rich context about a module for test generation."""

    module_path: str
    module_name: str
    import_path: str
    source_code: str
    module_docstring: str | None
    classes: list[dict[str, Any]]
    functions: list[dict[str, Any]]
    imports: list[str]
    dependencies: list[str]
    current_coverage: float
    uncovered_lines: list[int]
    uncovered_functions: list[str]
    similar_test_files: list[dict[str, Any]]
    external_deps: list[str]
    filesystem_usage: bool
    database_usage: bool
    network_usage: bool

    # ID: 02560995-d66d-493d-8896-138a623a8304
    def to_prompt_context(self) -> str:
        """Convert to formatted context for LLM prompt."""
        lines = []
        lines.append("# MODULE CONTEXT")
        lines.append(f"\n## Module: {self.module_path}")
        lines.append(f"Import as: `{self.import_path}`")
        if self.module_docstring:
            lines.append("\n## Purpose")
            lines.append(self.module_docstring)
        lines.append("\n## Coverage Status")
        lines.append(f"Current Coverage: {self.current_coverage:.1f}%")
        if self.uncovered_functions:
            lines.append(f"Uncovered Functions ({len(self.uncovered_functions)}):")
            for func in self.uncovered_functions[:10]:
                lines.append(f"  - {func}")
        lines.append("\n## Module Structure")
        if self.classes:
            lines.append(f"Classes ({len(self.classes)}):")
            for cls in self.classes:
                lines.append(
                    f"  - {cls['name']}: {cls.get('docstring', 'No description')[:80]}"
                )
        if self.functions:
            lines.append(f"Functions ({len(self.functions)}):")
            for func in self.functions:
                lines.append(
                    f"  - {func['name']}: {func.get('docstring', 'No description')[:80]}"
                )
        lines.append("\n## Dependencies to Mock")
        if self.external_deps:
            lines.append("External dependencies that MUST be mocked:")
            for dep in self.external_deps:
                lines.append(f"  - {dep}")
        if self.filesystem_usage:
            lines.append(
                "⚠️  This module uses filesystem operations - use tmp_path fixture!"
            )
        if self.database_usage:
            lines.append("⚠️  This module uses database - mock get_session()!")
        if self.network_usage:
            lines.append("⚠️  This module uses network - mock httpx requests!")
        if self.similar_test_files:
            lines.append("\n## Example Test Patterns from Similar Modules")
            for example in self.similar_test_files[:2]:
                lines.append(f"\n### Example from {example['file']}")
                lines.append("```python")
                lines.append(example["snippet"])
                lines.append("```")
        return "\n".join(lines)
