# src/will/agents/code_generation/context_formatters.py
# ID: b47a6286-ce4c-41be-ab54-b18b41f1f589

"""
Context formatting utilities for code generation prompts.

Formats:
- Dependencies from context items
- Similar symbol implementations
- Existing code context
"""

from __future__ import annotations


# ID: 28ef108d-9fd9-4396-9916-61dc592c46d1
def format_dependencies(items: list[dict]) -> str:
    """
    Format dependency information from context items.

    Args:
        items: Context items from ContextService

    Returns:
        Formatted dependency list as markdown string
    """
    deps = []
    seen = set()

    for item in items:
        if item.get("item_type") in ("code", "symbol"):
            name = item.get("name", "")
            path = item.get("path", "")
            sig = item.get("signature", "")

            if name and name not in seen:
                seen.add(name)
                deps.append(f"- `{name}` from `{path}`")
                if sig:
                    deps.append(f"  Signature: `{sig}`")

    return "\n".join(deps) if deps else "No specific dependencies found"


# ID: d437e305-28c7-4eac-ae9c-c7c5e964ad6c
def format_similar_symbols(items: list[dict]) -> str:
    """
    Format similar symbol implementations from context items.

    Args:
        items: Context items from ContextService

    Returns:
        Formatted similar symbols as markdown with code examples
    """
    similar = []

    for item in items:
        if item.get("item_type") == "code" and item.get("content"):
            name = item.get("name", "unknown")
            summary = item.get("summary", "")
            content = item.get("content", "")

            # Only include if we have actual code
            if content and len(content) > 50:
                similar.append(f"### {name}")
                if summary:
                    similar.append(f"{summary}")
                similar.append("```python")
                similar.append(content[:500])  # Limit code length
                if len(content) > 500:
                    similar.append("# ... (truncated)")
                similar.append("```")
                similar.append("")

    return "\n".join(similar) if similar else "No similar implementations found"


# ID: b11c6d48-69fa-4e67-9342-beddef91e667
def format_existing_code(items: list[dict], target_path: str | None) -> str:
    """
    Format existing code from the target file if available.

    Args:
        items: Context items from ContextService
        target_path: Target file path to find

    Returns:
        Formatted existing code as markdown code block
    """
    if not target_path:
        return ""

    for item in items:
        if item.get("path") == target_path and item.get("content"):
            content = item.get("content", "")
            if content:
                return f"```python\n{content}\n```"

    return ""
