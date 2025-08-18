# src/core/test_runner.py
"""
Core test execution capability for running pytest and interpreting results.
"""
import logging
import subprocess

logger = logging.getLogger(__name__)


def run_tests():
    """
    Run pytest and return a structured result indicating success or failure.
    Returns a dict with 'exit_code', 'summary', and 'stderr' keys.
    """
    logger.info("🧪 Running tests with pytest...")
    try:
        result = subprocess.run(
            ["pytest"],
            capture_output=True,
            text=True,
            check=False,
        )
        exit_code = str(result.returncode)
        stderr = result.stderr

        if result.returncode == 0:
            summary = "✅ Tests passed"
        else:
            summary = "❌ Tests failed"

        return {
            "exit_code": exit_code,
            "summary": summary,
            "stderr": stderr,
        }
    except FileNotFoundError:
        logger.error("Pytest not found: pytest is not installed")
        return {
            "exit_code": "1",
            "summary": "❌ pytest not found",
            "stderr": "pytest is not installed",
        }
