# src/shared/utils/parsing.py
"""
Shared utilities for parsing structured data from unstructured text,
primarily from Large Language Model (LLM) outputs.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, cast


# ID: 03987fc0-13ec-460a-a399-a89c7289eac6
def extract_json_from_response(text: str) -> dict[Any, Any] | list[Any] | None:
    """
    Extracts a JSON object or array from a raw text response, making it robust
    against common LLM formatting issues like introductory text.
    """
    # 1. Try to extract JSON from markdown code blocks
    json_data = _extract_from_markdown(text)
    if json_data is not None:
        return cast(dict[Any, Any] | list[Any], json_data)

    # 2. Fallback: Find raw JSON by matching braces/brackets
    return cast(dict[Any, Any] | list[Any] | None, _extract_raw_json(text))


def _extract_from_markdown(text: str) -> dict[Any, Any] | list[Any] | None:
    pattern = r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```"
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return None

    try:
        return cast(dict[Any, Any] | list[Any], json.loads(match.group(1)))
    except json.JSONDecodeError:
        return None


def _extract_raw_json(text: str) -> dict[Any, Any] | list[Any] | None:
    first_brace = text.find("{")
    first_bracket = text.find("[")

    if first_brace == -1 and first_bracket == -1:
        return None

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        end_char = "}"
        start_index = first_brace
    else:
        end_char = "]"
        start_index = first_bracket

    last_index = text.rfind(end_char)
    if last_index <= start_index:
        return None

    try:
        json_str = text[start_index : last_index + 1]
        return cast(dict[Any, Any] | list[Any], json.loads(json_str))
    except (json.JSONDecodeError, ValueError):
        return None


# ID: d4c82c76-0762-4358-b7b4-13d4819fce6c
def parse_write_blocks(text: str) -> dict[str, str]:
    """
    Parses a string for one or more [[write:file_path]]...[[/write]] blocks.
    """
    pattern = r"\[\[write:(.+?)\]\]\s*\n(.*?)\n\s*\[\[/write\]\]"
    matches = re.findall(pattern, text, re.DOTALL)
    return {path.strip(): content.strip() for path, content in matches}


def _normalize_python_snippet(code: str) -> str:
    """
    Normalize a Python snippet extracted from an LLM response.
    """
    if not code:
        return code

    lines = code.splitlines()
    if not lines:
        return code

    fixed_lines: list[str] = []
    for idx, line in enumerate(lines):
        if idx == 0:
            stripped = line.lstrip()
            if stripped.startswith(r"\n"):
                stripped = stripped[2:]
            if stripped.startswith("\\") and not stripped.startswith("\\\\"):
                stripped = stripped.lstrip("\\")
            fixed_lines.append(stripped)
        else:
            fixed_lines.append(line)

    normalized = "\n".join(fixed_lines).strip()
    try:
        ast.parse(normalized)
        return normalized
    except SyntaxError:
        return code


def _is_valid_python_block(code: str) -> bool:
    """
    Heuristic check to see if a block contains actual Python logic.
    Filters out blocks that are just comments or lack keywords.
    """
    if not code or not code.strip():
        return False

    lines = [line.strip() for line in code.splitlines() if line.strip()]
    if not lines:
        return False

    # Reject if every line is a comment
    if all(line.startswith("#") for line in lines):
        return False

    # Must contain at least one structural keyword
    keywords = {
        "def ",
        "class ",
        "import ",
        "from ",
        "@",
        "async def ",
        "return ",
        "assert ",
    }
    return any(any(k in line for k in keywords) for line in lines)


# ID: 44c9f1bf-9a35-46d1-8059-f0d82b745a58
def extract_python_code_from_response(text: str) -> str | None:
    """
    Extract Python code from an LLM response using a prioritized scoring strategy.
    """
    if not text:
        return None

    candidates = []

    pattern = r"```(\w*)\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)

    for lang, content in matches:
        cleaned = content.strip()
        if lang and lang.lower() not in ("python", "py", ""):
            continue

        if len(cleaned) > 10 and _is_valid_python_block(cleaned):
            candidates.append(cleaned)

    if not candidates:
        stripped = text.strip()
        if _is_valid_python_block(stripped):
            candidates.append(stripped)

    if not candidates:
        return None

    # ID: 46c042d9-977d-4567-9dff-4bb63bb042b0
    def score_candidate(code: str) -> float:
        score = 0.0
        if "def test_" in code:
            score += 1000
        if "class Test" in code:
            score += 1000
        if "import " in code or "from " in code:
            score += 100
        if "pytest" in code or "unittest" in code:
            score += 500
        score += min(len(code), 5000) / 10000.0
        return score

    candidates.sort(key=score_candidate, reverse=True)

    return cast(str, _normalize_python_snippet(candidates[0]))
