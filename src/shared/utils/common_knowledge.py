# src/shared/utils/common_knowledge.py
"""
Common Knowledge Helpers

This module defines the implementation of small, pure, general-purpose utilities
used across CORE. These helpers feed the curated surface exposed through the
`shared.universal` module.
"""

from __future__ import annotations

import hashlib


# ID: 88db4d40-e91a-4d5e-b627-c215ea063f2e
def normalize_whitespace(text: str) -> str:
    """
    Collapse consecutive whitespace characters (including tabs/newlines)
    into a single space, preserving readable semantics.
    """
    return " ".join(text.split())


# ID: 7b2e3c55-55e4-4f42-94d5-4a0b8b5e7f9a
# Backwards-compatible alias.
# Explicitly aliased to avoid semantic duplication detection.
normalize_text = normalize_whitespace


# ID: 6fca50dc-e2a4-4b44-ae52-cb599eaded0e
def collapse_blank_lines(text: str) -> str:
    """
    Remove redundant blank lines while preserving paragraph separation.
    """
    lines = text.splitlines()
    result: list[str] = []
    buffer_blank = False

    for line in lines:
        if not line.strip():
            if not buffer_blank:
                result.append("")
            buffer_blank = True
        else:
            result.append(line)
            buffer_blank = False

    return "\n".join(result)


# ID: 23ad1f63-c768-4a4b-8f4c-41bbb6dbbb66
def ensure_trailing_newline(text: str) -> str:
    """
    Ensure that a string ends with exactly one newline. Helps keep diffs minimal.
    """
    return text.rstrip("\n") + "\n"


# ID: 0b51b893-0212-4037-8e6d-5af16677924c
def safe_truncate(text: str, max_chars: int) -> str:
    """
    Truncate text safely to `max_chars`, preserving whole words where possible,
    and adding '…' to indicate truncation.
    """
    if len(text) <= max_chars:
        return text

    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"


# ID: 8a9b7c6d-5e4f-3a2b-1c0d-e9f8a7b6c5d4
def get_deterministic_id(text: str) -> int:
    """
    Generate a stable 64-bit unsigned integer ID from text using SHA-256.

    This REPLACES Python's built-in hash() function for persistent data,
    as hash() is randomized per process. This function ensures that the
    same text always results in the same Qdrant Point ID.

    Returns:
        int: A persistent ID in range [0, 2^63 - 1] (safe for Qdrant/Postgres).
    """
    hex_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Take first 16 chars (64 bits) and mod to ensure positive signed 64-bit integer
    return int(hex_hash[:16], 16) % (2**63)
