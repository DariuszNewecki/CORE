"""
Helper functions for ConversationalAgent.
Contains pure functions extracted from the main agent class.
"""

import re
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


def _create_task_spec(user_message: str, extract_keywords_func) -> dict[str, Any]:
    """
    Convert user message into a ContextBuilder task specification.

    This uses simple heuristics for now. Future: use local LLM for
    semantic understanding and smart scope detection.

    Args:
        user_message: Raw user input
        extract_keywords_func: Function to extract keywords from message

    Returns:
        Task spec for ContextBuilder
    """
    # Simple keyword extraction for scope hints
    # Future: Use local embedding model for semantic search
    keywords = extract_keywords_func(user_message)

    return {
        "task_id": f"chat-{hash(user_message) & 0xFFFFFFFF:08x}",
        "task_type": "conversational",
        "summary": user_message,
        "privacy": "local_only",
        "scope": {
            "include": keywords,  # ContextBuilder will use these as hints
            "exclude": [],
            "globs": [],
            "roots": [],
            "traversal_depth": 1,  # Keep it minimal for Phase 1
        },
        "constraints": {
            "max_tokens": 50000,  # Don't overwhelm the LLM
            "max_items": 30,  # Keep context focused
        },
    }


def _extract_keywords(message: str) -> list[str]:
    """
    Extract potential symbol names or file paths from user message.

    Simple implementation for Phase 1. Future: use local LLM embeddings
    for semantic similarity search.

    Args:
        message: User's natural language message

    Returns:
        List of keywords/symbols to search for
    """
    # Look for capitalized words (likely class names)
    # CamelCase or words with specific patterns
    keywords = []

    # Find CamelCase (e.g., ContextBuilder, CoreContext)
    camel_case = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", message)
    keywords.extend(camel_case)

    # Find snake_case (e.g., context_builder, build_for_task)
    snake_case = re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", message)
    keywords.extend(snake_case)

    # Find file paths (e.g., src/services/context/builder.py)
    file_paths = re.findall(r"\b(?:src/)?[\w/]+\.py\b", message)
    keywords.extend(file_paths)

    logger.debug(f"Extracted keywords: {keywords}")
    return keywords


def _build_llm_prompt(
    user_message: str,
    context_package: dict[str, Any],
    format_context_items_func,
) -> str:
    """
    Build the prompt to send to the LLM.

    Includes:
    - System context about CORE
    - The extracted context package
    - The user's question
    - Instructions for the LLM

    Args:
        user_message: Original user query
        context_package: Minimal context from ContextBuilder
        format_context_items_func: Function to format context items

    Returns:
        Complete prompt for LLM
    """
    # Extract key info from context package
    context_items = context_package.get("context", [])
    num_items = len(context_items)

    # Format context items for the LLM
    formatted_context = format_context_items_func(context_items)

    prompt = f"""You are CORE's conversational assistant, helping a developer understand their codebase.

The developer asked: "{user_message}"

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
        Formatted string representation
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
