# src/shared/utils/parsing.py
"""
Shared utilities for parsing structured data from unstructured text,
primarily from Large Language Model (LLM) outputs.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional


# ID: f2bd2480-f310-4090-ac1a-58ce05bfc4d3
def extract_json_from_response(text: str) -> Optional[Dict | List]:
    """
    Extracts a JSON object or array from a raw text response.
    Handles markdown code blocks (```json) and raw JSON.
    Returns None if no valid JSON is found.
    """
    # Pattern for JSON within a markdown block, now more lenient
    match = re.search(
        r"```(json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text, re.DOTALL
    )
    if match:
        # Group 2 will contain the JSON object or array
        json_str = match.group(2)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass  # Fall through to the next method if parsing fails

    # Fallback: Find the first '{' or '[' and try to parse from there
    try:
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace == -1 and start_bracket == -1:
            return None

        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            start_index = start_brace
        else:
            start_index = start_bracket

        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text[start_index:])
        return obj
    except (json.JSONDecodeError, ValueError):
        pass

    return None


# ID: 853be68b-f2d4-4494-bf4c-98200bc08026
def parse_write_blocks(text: str) -> Dict[str, str]:
    """
    Parses a string for one or more [[write:file_path]]...[[/write]] blocks.

    Args:
        text: The raw string output from an LLM.

    Returns:
        A dictionary where keys are file paths and values are the code blocks.
    """
    # Regex to find all occurrences of the write block pattern.
    # It captures the file path and the content between the tags.
    # re.DOTALL allows '.' to match newlines, which is crucial for multi-line code.
    pattern = re.compile(r"\[\[write:(.+?)\]\]\s*\n(.*?)\n\s*\[\[/write\]\]", re.DOTALL)

    matches = pattern.findall(text)

    # Return a dictionary comprehension of the found (path, content) tuples.
    # .strip() on the path and content cleans up any minor whitespace issues.
    return {path.strip(): content.strip() for path, content in matches}
