# src/will/test_generation/sandbox.py

"""
Pytest Sandbox Runner - Materialized Sensation.

Purpose:
- Execute generated tests in isolation.
- Materialize the 'Shadow Truth' (LimbWorkspace) to disk so subprocesses can see it.
- Return per-test results.

Constitutional Fix (V2.5.0):
- Ghost File Resolution: Materializes the entire LimbWorkspace into the temp dir.
- Sets PYTHONPATH to the temp dir so imports resolve to the 'Future Truth'.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)


@dataclass(frozen=True)
# ID: b3ecf72b-a9bf-4480-88f5-2f79f5ed1ddf
class SandboxResult:
    passed: bool  # Overall: True if ALL tests passed
    error: str = ""
    passed_tests: list[str] = None  # List of test function names that passed
    failed_tests: list[str] = None  # List of test function names that failed
    total_tests: int = 0

    def __post_init__(self):
        # Ensure lists are never None
        if self.passed_tests is None:
            object.__setattr__(self, "passed_tests", [])
        if self.failed_tests is None:
            object.__setattr__(self, "failed_tests", [])


# ID: 485df4ee-97b7-4685-a57b-4a470ce544c7
class PytestSandboxRunner:
    """Run generated tests via pytest with isolation, timeout, and Workspace Materialization."""

    def __init__(self, file_handler: FileHandler, repo_root: str):
        self._fh = file_handler
        self._repo_root = Path(repo_root)

    # ID: 49f91d78-3218-411d-b5f4-9cb3207853b4
    async def run(
        self,
        code: str,
        symbol_name: str,
        timeout_seconds: int = 30,
        workspace: LimbWorkspace | None = None,  # <--- NEW: Accept the Shadow Truth
    ) -> SandboxResult:
        """
        Execute code in a sandbox.
        If 'workspace' is provided, we materialize its uncommitted files
        so the test subprocess can import them.
        """
        # Unique ID for this run to avoid collision
        run_id = f"sandbox_{int(time.time())}_{symbol_name}"

        # We use a dedicated temp directory for the ENTIRE execution environment
        # This is safer than writing to var/canary inside the repo
        import tempfile

        with tempfile.TemporaryDirectory(prefix="core_sandbox_") as tmp_dir:
            sandbox_root = Path(tmp_dir)

            try:
                # 1. MATERIALIZATION: Replicate necessary context
                # If we have a workspace, dump its virtual files
                if workspace:
                    crate = workspace.get_crate_content()
                    for rel_path, content in crate.items():
                        # Determine dest path in sandbox
                        dst = sandbox_root / rel_path
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_text(content, encoding="utf-8")

                # 2. WRITE THE TEST
                # We place the test in a location that mimics the repo structure
                # to help relative imports work if necessary
                test_file_path = sandbox_root / f"test_{symbol_name}_sandbox.py"
                test_file_path.write_text(code, encoding="utf-8")

                # 3. CONFIGURE ENVIRONMENT
                # We append sandbox_root to PYTHONPATH so imports find the materialized files first
                env = os.environ.copy()
                original_pythonpath = env.get("PYTHONPATH", "")

                # Priority: Sandbox > Real Repo > System
                # This ensures we see "Future Truth" (Sandbox) before "Historical Truth" (Repo)
                env["PYTHONPATH"] = (
                    f"{sandbox_root}:{self._repo_root}/src:{self._repo_root}:{original_pythonpath}"
                )

                # 4. EXECUTE
                # We run pytest pointed specifically at our test file
                proc = await asyncio.create_subprocess_exec(
                    "pytest",
                    "-c",
                    "/dev/null",  # Ignore local pytest.ini
                    "-p",
                    "no:cov",  # Disable coverage (too slow/complex for sandbox)
                    "-p",
                    "no:cacheprovider",
                    "--tb=short",
                    "-v",
                    str(test_file_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=str(sandbox_root),  # CWD is the sandbox
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout_seconds
                    )
                except TimeoutError:
                    proc.kill()
                    return SandboxResult(
                        passed=False,
                        error=f"Execution timeout ({timeout_seconds}s).",
                        passed_tests=[],
                        failed_tests=[],
                        total_tests=0,
                    )

                output = stdout.decode(errors="replace") + stderr.decode(
                    errors="replace"
                )
                ok = proc.returncode == 0

                # 5. PARSE RESULTS
                passed_tests, failed_tests = self._parse_test_results(output)
                total = len(passed_tests) + len(failed_tests)

                return SandboxResult(
                    passed=ok,
                    error=("" if ok else output),
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                    total_tests=total,
                )

            except Exception as e:
                return SandboxResult(
                    passed=False,
                    error=str(e),
                    passed_tests=[],
                    failed_tests=[],
                    total_tests=0,
                )

    def _parse_test_results(self, output: str) -> tuple[list[str], list[str]]:
        """
        Parse pytest -v output.
        """
        passed = []
        failed = []

        # Regex to capture test names from verbose output
        # Example: test_file.py::test_func PASSED
        pattern = re.compile(r"(?:::)?([a-zA-Z_][a-zA-Z0-9_]*)\s+(PASSED|FAILED)")

        for match in pattern.finditer(output):
            test_name = match.group(1)
            status = match.group(2)

            if status == "PASSED":
                passed.append(test_name)
            elif status == "FAILED":
                failed.append(test_name)

        return passed, failed
