# src/shared/infrastructure/vector/adapters/constitutional/utils.py

"""
Shared utilities for constitutional vector adapters.

Pure utility functions used across chunker and item_builder modules.
"""

from __future__ import annotations

from typing import Any


# ID: safe-str
# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
def safe_str(value: Any) -> str:
    """
    Safely convert value to string.

    Handles None, str, and other types gracefully.

    Args:
        value: Any value to convert

    Returns:
        String representation (empty string for None)

    Examples:
        >>> safe_str(None)
        ''
        >>> safe_str("hello")
        'hello'
        >>> safe_str(42)
        '42'
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
