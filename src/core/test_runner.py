# src/core/test_runner.py
"""
Runs pytest against the local /tests directory and captures results.
This provides the core `test_execution` capability, allowing the system
to verify its own integrity after making changes.
"""
import subprocess
import os
import json
import datetime
from typing import Dict
from pathlib import Path
from shared.logger import getLogger
from shared.config import settings

log = getLogger(__name__)

# CAPABILITY: test_execution
def run_tests(silent: bool = True) -> Dict[str, str]:
    """Executes pytest on the tests/ directory and returns a structured result."""
    log.info("🧪 Running tests with pytest...")
    result = {
        "exit_code": "-1",
        "stdout": "",
        "stderr": "",
        "summary": "❌ Unknown error",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    repo_root = Path(__file__).resolve().parents[2]
    tests_path = repo_root / "tests"
    cmd = ["pytest", str(tests_path), "--tb=short", "-q"]

    timeout = os.getenv("TEST_RUNNER_TIMEOUT")
    try:
        timeout_val = int(timeout) if timeout else None
    except ValueError:
        timeout_val = None

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_val,
        )
        result["exit_code"] = str(proc.returncode)
        result["stdout"] = proc.stdout.strip()
        result["stderr"] = proc.stderr.strip()
        result["summary"] = _summarize(proc.stdout)

        if not silent:
            log.info(f"Pytest stdout:\n{proc.stdout}")
            if proc.stderr:
                log.warning(f"Pytest stderr:\n{proc.stderr}")

    except subprocess.TimeoutExpired:
        result["stderr"] = "Test run timed out."
        result["summary"] = "⏰ Timeout"
        log.error("Pytest run timed out.")
    except FileNotFoundError:
        result["stderr"] = "pytest is not installed or not found in PATH."
        result["summary"] = "❌ Pytest not available"
        log.error("Pytest command not found. Is it installed in the environment?")
    except Exception as e:
        result["stderr"] = str(e)
        result["summary"] = "❌ Test run error"
        log.error(f"An unexpected error occurred during test run: {e}", exc_info=True)

    _log_test_result(result)
    _store_failure_if_any(result)
    
    log.info(f"🏁 Test run complete. Summary: {result['summary']}")
    return result

def _summarize(output: str) -> str:
    """Parses pytest output to find the final summary line."""
    lines = output.strip().splitlines()
    for line in reversed(lines):
        if "passed" in line or "failed" in line or "error" in line:
            return line.strip()
    return "No test summary found."

def _log_test_result(data: Dict[str, str]):
    """Appends a JSON record of a test run to the persistent log file."""
    try:
        log_path = Path(settings.CORE_ACTION_LOG_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
    except Exception as e:
        log.warning(f"Failed to write to persistent test log file: {e}", exc_info=True)

def _store_failure_if_any(data: Dict[str, str]):
    """Saves the details of a failed test run to a dedicated file for easy access."""
    try:
        failure_path = Path("logs/test_failures.json")
        if data.get("exit_code") != "0":
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "summary": data.get("summary"),
                "stdout": data.get("stdout"),
                "timestamp": data.get("timestamp"),
            }
            failure_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        elif failure_path.exists():
            failure_path.unlink(missing_ok=True)
    except Exception as e:
        log.warning(f"Could not save test failure data: {e}", exc_info=True)