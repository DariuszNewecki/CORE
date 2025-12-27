# src/shared/infrastructure/validation/test_runner.py

"""
Executes pytest on the project's test suite and captures structured results for
system integrity verification.

Policy:
- No direct filesystem mutations outside governed mutation surfaces.
- Runtime artefact writes go through FileHandler runtime API (IntentGuard enforced).
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c70526bd-08f2-4c9b-b014-f4c548e188c6
def run_tests(silent: bool = True) -> dict[str, str]:
    """Executes pytest on the tests/ directory and returns a structured result."""
    logger.info("🧪 Running tests with pytest...")

    result: dict[str, str] = {
        "exit_code": "-1",
        "stdout": "",
        "stderr": "",
        "summary": "❌ Unknown error",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

    repo_root = Path(__file__).resolve().parents[3]
    tests_path = repo_root / "tests"
    cmd = ["pytest", str(tests_path), "--tb=short", "-q"]

    timeout = settings.model_extra.get("TEST_RUNNER_TIMEOUT", 300)

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=timeout
        )
        result["exit_code"] = str(proc.returncode)
        result["stdout"] = proc.stdout.strip()
        result["stderr"] = proc.stderr.strip()
        result["summary"] = _summarize(proc.stdout)

        if not silent:
            logger.info("Pytest stdout:\n%s", proc.stdout)
            if proc.stderr:
                logger.warning("Pytest stderr:\n%s", proc.stderr)

    except subprocess.TimeoutExpired:
        result["stderr"] = f"Test run timed out after {timeout}s."
        result["summary"] = "⏰ Timeout"
        logger.error("Pytest run timed out after %ss.", timeout)

    except FileNotFoundError:
        result["stderr"] = "pytest is not installed or not found in PATH."
        result["summary"] = "❌ Pytest not available"
        logger.error("Pytest command not found. Is it installed in the environment?")

    except Exception as e:
        result["stderr"] = str(e)
        result["summary"] = "❌ Test run error"
        logger.error(
            "An unexpected error occurred during test run: %s", e, exc_info=True
        )

    _log_test_result(result)
    _store_failure_if_any(result)

    logger.info("🏁 Test run complete. Summary: %s", result["summary"])
    return result


# ID: 9a8e5d43-624d-4a9c-bcc0-9b2d41e1e27e
def _summarize(output: str) -> str:
    """Parses pytest output to find the final summary line."""
    lines = output.strip().splitlines()
    for line in reversed(lines):
        if "passed" in line or "failed" in line or "error" in line:
            return line.strip()
    return "No test summary found."


# ID: 6f6c4f7a-2a64-4e3a-a0cf-4ef2a2d5c3a2
def _log_test_result(data: dict[str, str]) -> None:
    """Appends a JSON record of a test run to the persistent log file (via FileHandler)."""
    try:
        fh = FileHandler(str(settings.REPO_PATH))

        rel_log_path = _to_repo_relative_path(str(settings.CORE_ACTION_LOG_PATH))
        log_abs = (Path(settings.REPO_PATH).resolve() / rel_log_path).resolve()

        existing = ""
        if log_abs.exists():
            existing = log_abs.read_text(encoding="utf-8")

        new_line = json.dumps(data, ensure_ascii=False) + "\n"
        fh.write_runtime_text(rel_log_path, existing + new_line)

    except Exception as e:
        logger.warning(
            "Failed to write to persistent test log file: %s", e, exc_info=True
        )


# ID: 8d7aa550-3c1c-44c7-9c20-7c3c6b7b3a0d
def _store_failure_if_any(data: dict[str, str]) -> None:
    """Saves the details of a failed test run to a dedicated file (via FileHandler)."""
    try:
        fh = FileHandler(str(settings.REPO_PATH))
        failure_rel = "logs/test_failures.json"

        if data.get("exit_code") != "0":
            payload = {
                "summary": data.get("summary"),
                "stdout": data.get("stdout"),
                "timestamp": data.get("timestamp"),
            }
            fh.write_runtime_text(
                failure_rel, json.dumps(payload, indent=2, ensure_ascii=False)
            )
        else:
            fh.remove_file(failure_rel)

    except Exception as e:
        logger.warning("Could not save test failure data: %s", e, exc_info=True)


# ID: 4f5ab5a2-9c38-4b1d-8f77-7a2b1c2a7d23
def _to_repo_relative_path(path_str: str) -> str:
    """
    Convert a path to a repo-relative POSIX path.

    - If already relative: normalize and return.
    - If absolute under REPO_PATH: relativize.
    - If absolute outside repo: raise.
    """
    p = Path(path_str)
    if not p.is_absolute():
        return p.as_posix().lstrip("./")

    repo_root = Path(settings.REPO_PATH).resolve()
    resolved = p.resolve()

    if resolved.is_relative_to(repo_root):
        return resolved.relative_to(repo_root).as_posix()

    raise ValueError(f"Path is outside repository boundary: {path_str}")
