# src/will/phases/canary/pytest_runner.py

"""
Pytest execution for the canary phase and TestRunnerSensor, in the sandbox.

The tests run in the sandbox runner (ADR-132 D10.10), never as a pytest
subprocess of the services account. A run that did not happen, or ran only
in part (the service excludes integration tests), is not a result: it raises
``TestsNotRun`` so callers keep their evidence open instead of reading it as
a pass (lessons register L1).
"""

from __future__ import annotations

from body.sandbox.repo_tests import run_in_sandbox
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)

_CFG = load_operational_config().testing
TIMEOUT_EXIT_CODE = 124


# ID: 3d7f67c4-f56b-489a-a0da-831876a74180
class TestsNotRun(RuntimeError):
    """The sandbox did not run the tests (or ran them only in part)."""

    __test__ = False  # not a pytest test class


# ID: a68a1332-b69e-4e01-b1aa-d113fe4ba28b
class PytestRunner:
    """Runs pytest targets of the repository in the sandbox."""

    def __init__(
        self,
        path_resolver: PathResolver,
        execution_timeout: int = _CFG.pytest_execution_timeout_sec,
    ):
        self._paths = path_resolver
        self.execution_timeout = execution_timeout

    # ID: c09109f2-9052-4b20-b2b8-f3f04e027832
    async def run_tests(self, test_paths: list[str]) -> dict:
        """
        Run pytest on *test_paths* (repo-relative) in the sandbox.

        Returns dict with ``passed``, ``failed``, ``exit_code`` (0 = every
        test passed; 124 = timed out) and ``output``; ``output`` lists each
        failed test as ``FAILED <node id>``. Raises ``TestsNotRun`` when the
        sandbox did not run them in full.
        """
        result = await run_in_sandbox(
            self._paths.repo_root,
            test_paths,
            timeout_sec=self.execution_timeout,
        )
        counts = result.counts
        if result.status == "timeout":
            logger.error("Tests timed out after %ds", self.execution_timeout)
            return {
                "passed": counts.get("passed", 0),
                "failed": max(counts.get("failed", 0), 1),
                "exit_code": TIMEOUT_EXIT_CODE,
                "output": f"Tests timed out after {self.execution_timeout} seconds",
            }
        if result.status not in ("passed", "failed") or (
            result.status == "passed" and result.completeness != "full"
        ):
            raise TestsNotRun(f"{result.status}: {result.reason}")

        output = "\n".join(s for s in (result.stdout, result.stderr) if s)
        listed = "\n".join(f"FAILED {nodeid}" for nodeid in result.failed_ids)
        return {
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "exit_code": 0 if result.ok else (result.exit_code or 1),
            "output": f"{output}\n{listed}" if listed else output,
        }
