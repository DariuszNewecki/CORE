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

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "test_results.log"
FAILURE_FILE = LOG_DIR / "test_failures.json"
LOG_DIR.mkdir(exist_ok=True)

# CAPABILITY: test_execution
def run_tests(silent: bool = True) -> Dict[str, str]:
    """
    Executes pytest on the tests/ directory and returns a structured result.
    This function captures stdout, stderr, and the exit code, providing a
    comprehensive summary of the test run for agents to act upon.
    """
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
            print(proc.stdout)
            if proc.stderr:
                print("⚠️ stderr:", proc.stderr)

    except subprocess.TimeoutExpired:
        result["stderr"] = "Test run timed out."
        result["summary"] = "⏰ Timeout"
    except FileNotFoundError:
        result["stderr"] = "pytest is not installed or not found in PATH."
        result["summary"] = "❌ Pytest not available"
    except Exception as e:
        result["stderr"] = str(e)
        result["summary"] = "❌ Test run error"

    _log_test_result(result)
    _store_failure_if_any(result)
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
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
    except Exception as e:
        print(f"Warning: Failed to write test log: {e}")

def _store_failure_if_any(data: Dict[str, str]):
    """Saves the details of a failed test run to a dedicated file for easy access."""
    try:
        if data.get("exit_code") != "0":
            with open(FAILURE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "summary": data.get("summary"),
                    "stdout": data.get("stdout"),
                    "timestamp": data.get("timestamp")
                }, f, indent=2)
        elif os.path.exists(FAILURE_FILE):
            os.remove(FAILURE_FILE)
    except Exception as e:
        print(f"Warning: Could not save test failure data: {e}")