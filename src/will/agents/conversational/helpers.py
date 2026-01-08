# src/will/agents/conversational/helpers.py

"""
Helper functions for ConversationalAgent.
Contains pure functions extracted from the main agent class.

V2 (v2.2.0): RequestInterpreter now handles intent parsing and keyword extraction.
These helpers focus on bridging TaskStructure → ContextBuilder and formatting.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


def _build_llm_prompt(
    user_message: str,
    context_package: dict[str, Any],
    format_context_items_func,
    task_context: str = "",
) -> str:
    """
    Build the prompt to send to the LLM.

    Includes:
    - System context about CORE
    - Task interpretation metadata (if provided)
    - The extracted context package
    - The user's question
    - Instructions for the LLM

    Args:
        user_message: Original user query
        context_package: Minimal context from ContextBuilder
        format_context_items_func: Function to format context items
        task_context: Optional task interpretation metadata from RequestInterpreter

    Returns:
        Complete prompt for LLM
    """
    # Extract key info from context package
    context_items = context_package.get("context", [])
    num_items = len(context_items)

    # Format context items for the LLM
    formatted_context = format_context_items_func(context_items)

    # Build prompt with optional task context
    task_section = f"\n{task_context}\n" if task_context else ""

    prompt = f"""You are CORE's conversational assistant, helping a developer understand their codebase.

The developer asked: "{user_message}"
{task_section}
I've extracted {num_items} relevant pieces of context from the codebase:

{formatted_context}

Please provide a clear, concise answer to their question based on this context.

Instructions:
- Focus on answering their specific question
- Use code examples from the context when helpful
- Be conversational and friendly
- If the context doesn't contain enough information, say so
- Keep your response under 500 words

Your response:"""

    return prompt


def _format_context_items(items: list[dict[str, Any]]) -> str:
    """
    Format context items into readable text for LLM.

    Args:
        items: List of context items from ContextPackage

    Returns:
        Formatted string representation with structure and code
    """
    if not items:
        return "(No specific context found - the question may be too general)"

    formatted = []
    for i, item in enumerate(items, 1):
        name = item.get("name", "Unknown")
        item_type = item.get("item_type", "unknown")
        path = item.get("path", "")
        summary = item.get("summary", "")
        content = item.get("content", "")

        formatted.append(f"--- Context Item {i}: {name} ({item_type}) ---")
        if path:
            formatted.append(f"Location: {path}")
        if summary:
            formatted.append(f"Summary: {summary}")
        if content:
            # Truncate very long content
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
            formatted.append(f"Code:\n{content}")
        formatted.append("")  # Blank line between items

    return "\n".join(formatted)
