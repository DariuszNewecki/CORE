# src/shared/utils/parsing.py
"""
Shared utilities for parsing structured data from unstructured text,
primarily from Large Language Model (LLM) outputs.
"""

from __future__ import annotations

import json
import re


# ID: f2bd2480-f310-4090-ac1a-58ce05bfc4d3
def extract_json_from_response(text: str) -> dict | list | None:
    """
    Extracts a JSON object or array from a raw text response, making it robust
    against common LLM formatting issues like introductory text.

    Args:
        text: Raw text response that may contain JSON.

    Returns:
        Parsed JSON as a dictionary or list, or None if no valid JSON found.
    """
    # 1. Try to extract JSON from markdown code blocks
    json_data = _extract_from_markdown(text)
    if json_data is not None:
        return json_data

    # 2. Fallback: Find raw JSON by matching braces/brackets
    return _extract_raw_json(text)


def _extract_from_markdown(text: str) -> dict | list | None:
    """
    Attempts to extract JSON from a markdown code block.

    Args:
        text: Text that may contain a markdown JSON block.

    Returns:
        Parsed JSON or None if extraction fails.
    """
    pattern = r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```"
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _extract_raw_json(text: str) -> dict | list | None:
    """
    Extracts JSON by finding the outermost braces or brackets.
    Robust against extra text before or after the JSON.

    Args:
        text: Text that may contain raw JSON.

    Returns:
        Parsed JSON or None if extraction fails.
    """
    first_brace = text.find("{")
    first_bracket = text.find("[")

    # No JSON markers found
    if first_brace == -1 and first_bracket == -1:
        return None

    # Determine which comes first: object or array
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        end_char = "}"
        start_index = first_brace
    else:
        end_char = "]"
        start_index = first_bracket

    # Find the matching closing character
    last_index = text.rfind(end_char)
    if last_index <= start_index:
        return None

    try:
        json_str = text[start_index : last_index + 1]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


# ID: 853be68b-f2d4-4494-bf4c-98200bc08026
def parse_write_blocks(text: str) -> dict[str, str]:
    """
    Parses a string for one or more [[write:file_path]]...[[/write]] blocks.

    Args:
        text: The raw string output from an LLM.

    Returns:
        A dictionary where keys are file paths and values are the code blocks.

    Example:
        >>> text = "[[write:test.py]]\\nprint('hello')\\n[[/write]]"
        >>> parse_write_blocks(text)
        {'test.py': "print('hello')"}
    """
    pattern = r"\[\[write:(.+?)\]\]\s*\n(.*?)\n\s*\[\[/write\]\]"
    matches = re.findall(pattern, text, re.DOTALL)
    return {path.strip(): content.strip() for path, content in matches}
