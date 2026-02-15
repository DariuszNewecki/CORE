# src/shared/infrastructure/vector/adapters/constitutional/utils.py

"""
Shared utilities for constitutional vector adapters.

Pure utility functions used across chunker and item_builder modules.
"""

from __future__ import annotations

from typing import Any


# ID: 980e2532-9ff1-4205-ab20-d55e27364e5e
# ID: 1f60cc93-ae61-4f3c-ab15-d4021b3617a7
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
