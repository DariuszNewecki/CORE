# src/will/tools/context/formatter.py
"""
Markdown formatter for architectural context.
Turns structured context data into high-fidelity LLM prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .models import ArchitecturalContext


# ID: 51a52f37-a84f-42ef-aba7-e776032a979c
def format_context_to_markdown(context: ArchitecturalContext) -> str:
    """
    Transforms the ArchitecturalContext dataclass into a formatted Markdown block.
    Preserves the 'Strict Focus' requirements for the LLM.
    """
    parts = [
        "# Architectural Context",
        "",
        f"**Goal:** {context.goal}",
        f"**Target Layer:** {context.target_layer}",
        f"**Layer Purpose:** {context.layer_purpose}",
        f"**Placement Confidence:** {context.placement_confidence}",
        "",
    ]

    # 1. Target File Section (Crucial for Test Generation)
    if context.target_file_content and context.target_file_path:
        parts.extend(
            [
                "## Target File to Test",
                f"**File:** {context.target_file_path}",
                "",
                "```python",
                context.target_file_content,
                "```",
                "",
                "**CRITICAL:** Generate tests for the ACTUAL models shown above.",
                "Do NOT hallucinate User, Project, or other models not present in the file.",
                "",
            ]
        )

    # 2. Standards & Patterns
    if context.layer_patterns:
        parts.append("## Layer Patterns")
        parts.extend([f"- {p}" for p in context.layer_patterns])
        parts.append("")

    if context.typical_dependencies:
        parts.append("## Typical Dependencies")
        parts.extend([f"- {d}" for d in context.typical_dependencies])
        parts.append("")

    if context.anti_patterns:
        parts.append("## Anti-Patterns to Avoid")
        parts.extend([f"- {a}" for a in context.anti_patterns])
        parts.append("")

    # 3. Semantic References
    if context.similar_examples:
        parts.append("## Similar Examples for Reference")
        for ex in context.similar_examples[:3]:
            parts.extend(
                [
                    f"### {ex.symbol_name} ({ex.file_path})",
                    f"**Purpose:** {ex.purpose}",
                    "```python",
                    ex.code_snippet,
                    "```",
                    "",
                ]
            )

    if context.relevant_policies:
        parts.append("## Relevant Constitutional Policies")
        for policy in context.relevant_policies[:3]:
            stmt = policy.get("statement", "No statement provided.")
            parts.append(f"- {stmt}")
        parts.append("")

    return "\n".join(parts)
