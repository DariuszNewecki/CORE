# src/shared/ai/response_parser.py
# ID: shared.ai.response_parser
"""
response_parser — shared utility for parsing LLM responses.

LLMs frequently wrap output in markdown fences (```json ... ```, ```python ... ```)
despite instructions to the contrary. This module provides the canonical
extraction logic so every call site handles it consistently.

Constitutional context:
- All AI responses flow through PromptModel.invoke()
- Callers that need JSON must parse the string returned by invoke()
- Callers that need raw code must strip fences before passing to FileHandler
- This module is the single, canonical implementation for both steps

Usage:
    from shared.ai.response_parser import extract_json, extract_code

    raw = await model.invoke(context, client)
    data = extract_json(raw)       # for JSON responses
    code = extract_code(raw)       # for Python/code responses
"""

from __future__ import annotations

import json
import re
from typing import Any


# Matches ```<lang> ... ``` or ``` ... ``` (with optional whitespace)
_FENCE_RE = re.compile(
    r"```(?:\w+)?\s*\n?([\s\S]*?)\n?\s*```",
    re.DOTALL,
)


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567891
def extract_json(text: str) -> Any:
    """
    Extract and parse JSON from an LLM response string.

    Handles two common response formats:
    1. Plain JSON — the model returned raw JSON as instructed
    2. Fenced JSON — the model wrapped its response in ```json ... ``` or ``` ... ```

    Args:
        text: Raw string returned by an LLM invocation.

    Returns:
        Parsed Python object (dict, list, etc.).

    Raises:
        json.JSONDecodeError: If no valid JSON can be extracted.
        ValueError: If the input is empty.
    """
    if not text or not text.strip():
        raise ValueError("LLM response is empty — cannot extract JSON.")

    match = _FENCE_RE.search(text)
    if match:
        return json.loads(match.group(1).strip())

    return json.loads(text.strip())


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678902
def extract_json_safe(text: str, default: Any = None) -> Any:
    """
    Like extract_json but returns `default` instead of raising on failure.

    Args:
        text: Raw string returned by an LLM invocation.
        default: Value to return if extraction fails. Defaults to None.

    Returns:
        Parsed Python object or `default` on any failure.
    """
    try:
        return extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return default


# ID: c3d4e5f6-a7b8-9012-cdef-123456789013
def extract_code(text: str) -> str:
    """
    Strip markdown code fences from an LLM response containing raw code.

    Handles ```python ... ```, ```py ... ```, and plain ``` ... ``` wrappers.
    Models frequently wrap code output in fences despite instructions.
    The FileHandler syntax gate will reject fenced content — this must be
    called before any .py content is passed to a Crate or FileHandler.

    Args:
        text: Raw string returned by an LLM invocation.

    Returns:
        Clean code string with fences removed.
    """
    if not text or not text.strip():
        return text
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped
