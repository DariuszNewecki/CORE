# src/core/ruff_linter.py

"""
Runs Ruff lint checks on generated Python code before it's staged.

Returns a success flag and an optional linting message.
"""

import subprocess
import tempfile
import os
from typing import Tuple


def fix_and_lint_code_with_ruff(code: str, display_filename: str = "<code>") -> Tuple[bool, str, str]:
    """
    Fix and lint the provided Python code using Ruff.

    Args:
        code (str): Source code to fix and lint.
        display_filename (str): Optional display name (e.g., intended file path).

    Returns:
        (is_clean: bool, message: str, fixed_code: str)
    """
    tmp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp_file:
            tmp_file.write(code)
            tmp_file_path = tmp_file.name

        result = subprocess.run(
            ["ruff", "check", tmp_file_path, "--fix", "--exit-zero", "--quiet", "--ignore=D417,D401,D213,D407"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Read the fixed code back from the temporary file
        with open(tmp_file_path, "r") as f:
            fixed_code = f.read()

        # Check if there are any remaining errors
        if result.stdout.strip():
            # Replace temp path in output with the expected file path for user readability
            readable_output = result.stdout.replace(tmp_file_path, display_filename)
            return False, readable_output.strip(), fixed_code

        return True, "", fixed_code

    except FileNotFoundError:
        return False, "Ruff is not installed or not in your PATH. Please install it to enable lint checks.", code

    except Exception as e:
        return False, f"Ruff execution failed: {e}", code

    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception:
                pass  # Don't crash if temp cleanup fails