# src/shared/utils/parsing.py
"""
Shared utilities for parsing structured data from unstructured text,
primarily from Large Language Model (LLM) outputs.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional


def extract_json_from_response(text: str) -> Optional[Dict | List]:
    """
    Extracts a JSON object or array from a raw text response.
    Handles markdown code blocks (```json) and raw JSON.
    Returns None if no valid JSON is found.
    """
    # Pattern for JSON within a markdown block
    match = re.search(r"```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        start_index = text.find("{")
        if start_index == -1 or (text.find("[") != -1 and text.find("[") < start_index):
            start_index = text.find("[")

        if start_index != -1:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(text[start_index:])
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    return None


# --- THIS IS THE NEW, MISSING FUNCTION ---
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
