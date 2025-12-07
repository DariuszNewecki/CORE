# src/services/validation/ruff_linter.py

"""
Provides a utility to fix and lint Python code using Ruff's JSON output format.
Runs Ruff lint checks on generated Python code before it's staged.
Returns a success flag and an optional linting message.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from shared.logger import getLogger

logger = getLogger(__name__)
Violation = dict[str, Any]


# ID: 4c86e6d0-20f6-4773-8030-b31d1d109871
def fix_and_lint_code_with_ruff(
    code: str, display_filename: str = "<code>"
) -> tuple[str, list[Violation]]:
    """
    Fix and lint the provided Python code using Ruff's JSON output format.

    Args:
        code (str): Source code to fix and lint.
        display_filename (str): Optional display name for readable error messages.

    Returns:
        A tuple containing:
        - The potentially fixed code as a string.
        - A list of structured violation dictionaries for any remaining issues.
    """
    violations = []
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w+", delete=False, encoding="utf-8"
    ) as tmp_file:
        tmp_file.write(code)
        tmp_file_path = tmp_file.name
    try:
        subprocess.run(
            ["ruff", "check", tmp_file_path, "--fix", "--exit-zero", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
        )
        with open(tmp_file_path, encoding="utf-8") as f:
            fixed_code = f.read()
        result = subprocess.run(
            ["ruff", "check", tmp_file_path, "--format", "json", "--exit-zero"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            ruff_violations = json.loads(result.stdout)
            for v in ruff_violations:
                violations.append(
                    {
                        "rule": v.get("code", "RUFF-UNKNOWN"),
                        "message": v.get("message", "Unknown Ruff error"),
                        "line": v.get("location", {}).get("row", 0),
                        "severity": "warning",
                    }
                )
        return (fixed_code, violations)
    except FileNotFoundError:
        logger.error("Ruff is not installed or not in your PATH. Please install it.")
        tool_missing_violation = {
            "rule": "tooling.missing",
            "message": "Ruff is not installed or not in your PATH.",
            "line": 0,
            "severity": "error",
        }
        return (code, [tool_missing_violation])
    except json.JSONDecodeError:
        logger.error("Failed to parse Ruff's JSON output.")
        return (code, [])
    except Exception as e:
        logger.error("An unexpected error occurred during Ruff execution: %s", e)
        return (code, [])
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
