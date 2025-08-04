# src/core/black_formatter.py
"""
Formats Python code using Black before it's written to disk.
"""

import black
from typing import Tuple, Optional


def format_code_with_black(code: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to format the given Python code using Black.

    Returns:
        Tuple:
            - formatted_code (str) if successful, else None
            - error_message (str) if failed, else None
    """
    try:
        mode = black.FileMode()
        formatted_code = black.format_str(code, mode=mode)
        return formatted_code, None
    except Exception as e:
        return None, f"Black formatting failed: {str(e)}"
