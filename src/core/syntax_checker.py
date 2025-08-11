# src/core/syntax_checker.py
"""
A simple syntax checker utility.
Validates the syntax of Python code before it's staged for write/commit.
"""
import ast
from typing import List, Dict, Any

Violation = Dict[str, Any]

# --- MODIFICATION: The function now returns a list of structured violation dictionaries. ---
# CAPABILITY: syntax_validation
def check_syntax(file_path: str, code: str) -> List[Violation]:
    """Checks the given Python code for syntax errors and returns a list of violations, if any."""
    """
    Checks whether the given code has valid Python syntax.

    Args:
        file_path (str): File name (used to detect .py files).
        code (str): Source code string.

    Returns:
        A list of violation dictionaries. An empty list means the syntax is valid.
    """
    if not file_path.endswith(".py"):
        return []

    try:
        ast.parse(code)
        return []
    except SyntaxError as e:
        error_line = e.text.strip() if e.text else "<source unavailable>"
        return [{
            "rule": "E999", # Ruff's code for syntax errors
            "message": f"Invalid Python syntax: {e.msg} near '{error_line}'",
            "line": e.lineno,
            "severity": "error"
        }]