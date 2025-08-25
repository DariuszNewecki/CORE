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
            # Fall through to the next method if markdown block is malformed
            pass
    # Pattern for raw JSON object/array at the start of a string
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
