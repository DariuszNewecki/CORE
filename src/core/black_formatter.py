# src/core/black_formatter.py
"""
Formats Python code using Black before it's written to disk.
"""
import black


# --- MODIFICATION: The function now returns only the formatted code on success ---
# --- and raises a specific exception on failure, simplifying its contract. ---
def format_code_with_black(code: str) -> str:
    """Formats the given Python code using Black, raising `black.InvalidInput` for syntax errors or `Exception` for other formatting issues."""
    """
    Attempts to format the given Python code using Black.

    Args:
        code: The Python source code to format.

    Returns:
        The formatted code as a string.

    Raises:
        black.InvalidInput: If the code contains a syntax error that Black cannot handle.
        Exception: For other unexpected Black formatting errors.
    """
    try:
        mode = black.FileMode()
        formatted_code = black.format_str(code, mode=mode)
        return formatted_code
    except black.InvalidInput as e:
        # Re-raise with a clear message for the pipeline to catch.
        raise black.InvalidInput(
            f"Black could not format the code due to a syntax error: {e}"
        )
    except Exception as e:
        # Catch any other unexpected errors from Black.
        raise Exception(f"An unexpected error occurred during Black formatting: {e}")
