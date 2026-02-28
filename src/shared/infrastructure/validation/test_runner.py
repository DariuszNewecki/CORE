# src/shared/infrastructure/validation/test_runner.py
# ID: c70526bd-08f2-4c9b-b014-f4c548e188c6

"""
Executes pytest and captures results as Constitutional Evidence.

- Implemented 'silent' parameter to control logging verbosity (workflow.dead_code_check).
- Maintains strict traceability by persisting to DB regardless of verbosity.
- Aligns with the 'Headless' policy (LOG-001).
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any

from shared.action_types import ActionImpact, ActionResult
from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0a702b47-f04b-4afe-8e35-20e9cad19aa3
async def run_tests(silent: bool = True) -> ActionResult:
    """
    Executes pytest asynchronously and returns a canonical ActionResult.

    Args:
        silent: If False, logs start/stop events to the system logger.
    """
    start_time = time.perf_counter()

    if not silent:
        logger.info("🧪 Initiating system test suite...")

    repo_root = settings.REPO_PATH
    tests_path = repo_root / "tests"

    timeout = settings.model_extra.get("TEST_RUNNER_TIMEOUT", 300)

    try:
        process = await asyncio.create_subprocess_exec(
            "pytest",
            str(tests_path),
            "--tb=short",
            "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=repo_root,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode().strip()
            stderr = stderr_bytes.decode().strip()
            exit_code = process.returncode
        except TimeoutError:
            process.kill()
            stdout = ""
            stderr = f"Test run timed out after {timeout}s."
            exit_code = -1

    except Exception as e:
        stdout = ""
        stderr = str(e)
        exit_code = -1

    duration = time.perf_counter() - start_time
    ok = exit_code == 0
    summary = (
        _summarize(stdout) if ok else (stderr.split("\n")[0] or "Execution failed")
    )

    # 1. Construct the Result Payload
    result_data = {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
        "error": summary if not ok else None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # 2. Build the Canonical ActionResult
    action_result = ActionResult(
        action_id="test_execution",
        ok=ok,
        data=result_data,
        duration_sec=duration,
        impact=ActionImpact.READ_ONLY,
        suggestions=["Run 'pytest --lf' to retry failed tests."] if not ok else [],
    )

    # 3. Persist Evidence (Always happens, even if silent)
    _log_test_result_to_file(result_data)
    _store_failure_artifact(result_data)
    await _persist_result_to_db(action_result)

    if not silent:
        logger.info("🏁 Test run complete: %s (%.2fs)", summary, duration)

    return action_result


def _summarize(output: str) -> str:
    """Parses pytest output to find the final summary line."""
    if not output:
        return "No output captured."
    lines = output.strip().splitlines()
    for line in reversed(lines):
        if any(word in line for word in ["passed", "failed", "error", "skipped"]):
            return line.strip()
    return "No test summary found."


async def _persist_result_to_db(result: ActionResult) -> None:
    """Writes the result to the core.action_results table."""
    from shared.models.action_result import ActionResult as ActionResultModel

    try:
        async with get_session() as session:
            db_entry = ActionResultModel(
                action_type="test_execution",
                ok=result.ok,
                error_message=result.data.get("stderr") if not result.ok else None,
                action_metadata={
                    "summary": result.data.get("summary"),
                    "exit_code": result.data.get("exit_code"),
                    "timestamp": result.data.get("timestamp"),
                },
                agent_id="test_runner_infra",
                duration_ms=int(result.duration_sec * 1000),
            )
            session.add(db_entry)
            await session.commit()
    except Exception as e:
        logger.warning("Failed to persist test result to DB: %s", e)


def _log_test_result_to_file(data: dict[str, Any]) -> None:
    try:
        fh = FileHandler(str(settings.REPO_PATH))
        rel_log_path = "var/logs/tests.jsonl"
        new_line = json.dumps(data, ensure_ascii=False) + "\n"
        fh.write_runtime_text(rel_log_path, new_line)
    except Exception as e:
        logger.debug("Test file logging skipped: %s", e)


def _store_failure_artifact(data: dict[str, Any]) -> None:
    try:
        fh = FileHandler(str(settings.REPO_PATH))
        failure_rel = "var/reports/test_failures.json"
        if data.get("exit_code") != 0:
            fh.write_runtime_json(failure_rel, data)
        else:
            fh.remove_file(failure_rel)
    except Exception as e:
        logger.debug("Test failure artifact update skipped: %s", e)
