# src/core/syntax_checker.py

"""
A simple syntax checker utility.

Validates the syntax of Python code before it's staged for write/commit.
"""

import ast
from typing import Tuple


# CAPABILITY: syntax_validation
def check_syntax(file_path: str, code: str) -> Tuple[bool, str]:
    """
    Checks whether the given code has valid syntax.

    Args:
        file_path (str): File name (used to detect .py files)
        code (str): Source code string

    Returns:
        (is_valid: bool, message: str)
    """
    if not file_path.endswith(".py"):
        return True, "Syntax check skipped for non-Python file."

    try:
        ast.parse(code)
        return True, "Python syntax is valid."
    except SyntaxError as e:
        # In rare cases, e.text may be None
        error_line = e.text.strip() if e.text else "<source unavailable>"
        return False, (
            f"Invalid Python syntax:\n"
            f"{error_line}\n"
            f"Line {e.lineno}, column {e.offset}: {e.msg}"
        )