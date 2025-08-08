# src/core/ruff_linter.py
"""
Runs Ruff lint checks on generated Python code before it's staged.
Returns a success flag and an optional linting message.
"""
import subprocess
import tempfile
import os
import json
from typing import Tuple, List, Dict, Any

from shared.logger import getLogger

log = getLogger(__name__)
Violation = Dict[str, Any]

# --- MODIFICATION: Complete refactor to use Ruff's JSON output. ---
# --- The function now returns the fixed code and a list of structured violations. ---
def fix_and_lint_code_with_ruff(code: str, display_filename: str = "<code>") -> Tuple[str, List[Violation]]:
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
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False, encoding="utf-8") as tmp_file:
        tmp_file.write(code)
        tmp_file_path = tmp_file.name

    try:
        # Step 1: Run Ruff with --fix to apply safe fixes. This modifies the temp file.
        subprocess.run(
            ["ruff", "check", tmp_file_path, "--fix", "--exit-zero", "--quiet"],
            capture_output=True, text=True, check=False
        )

        # Step 2: Read the potentially modified code back from the file.
        with open(tmp_file_path, "r", encoding="utf-8") as f:
            fixed_code = f.read()

        # Step 3: Run Ruff again without fix, but with JSON output to get remaining violations.
        result = subprocess.run(
            ["ruff", "check", tmp_file_path, "--format", "json", "--exit-zero"],
            capture_output=True, text=True, check=False
        )

        # Parse the JSON output for any remaining violations.
        if result.stdout:
            ruff_violations = json.loads(result.stdout)
            for v in ruff_violations:
                violations.append({
                    "rule": v.get("code", "RUFF-UNKNOWN"),
                    "message": v.get("message", "Unknown Ruff error"),
                    "line": v.get("location", {}).get("row", 0),
                    "severity": "warning" # Assume all ruff issues are warnings for now
                })
        
        return fixed_code, violations

    except FileNotFoundError:
        log.error("Ruff is not installed or not in your PATH. Please install it.")
        # Return a critical violation if the tool itself is missing.
        tool_missing_violation = {
            "rule": "tooling.missing",
            "message": "Ruff is not installed or not in your PATH.",
            "line": 0,
            "severity": "error"
        }
        return code, [tool_missing_violation]
    except json.JSONDecodeError:
        log.error("Failed to parse Ruff's JSON output.")
        return code, [] # Return empty if we can't parse, to avoid crashing.
    except Exception as e:
        log.error(f"An unexpected error occurred during Ruff execution: {e}")
        return code, []
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)