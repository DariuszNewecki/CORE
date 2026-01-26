# src/features/test_generation/sandbox.py

"""
Pytest Sandbox Runner

Purpose:
- Execute generated tests in isolation.
- Return per-test results (not just overall pass/fail).
- Enable extraction of passing tests from files with mixed results.

Constitutional Fix:
- -c /dev/null ignores repo pytest config.
- -p no:cov disables coverage plugin in sandbox.
- Parses pytest output to identify which individual tests passed.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass

from shared.infrastructure.storage.file_handler import FileHandler


@dataclass(frozen=True)
# ID: e5e9db6a-3e15-4f9d-9d86-c2c77ff09c8a
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


# ID: 4f0fd4d8-13de-49fd-9f8a-8b0f9c9727e4
class PytestSandboxRunner:
    """Run generated tests via pytest with isolation and timeout."""

    def __init__(self, file_handler: FileHandler, repo_root: str):
        self._fh = file_handler
        self._repo_root = repo_root

    # ID: 9ebca644-4365-4fcc-a1b4-a2ab2f7509d5
    async def run(
        self, code: str, symbol_name: str, timeout_seconds: int = 30
    ) -> SandboxResult:
        temp_rel_path = f"var/canary/test_{symbol_name}_{int(time.time())}.py"

        try:
            self._fh.write_runtime_text(temp_rel_path, code)
            abs_temp_path = self._fh._resolve_repo_path(temp_rel_path)

            env = os.environ.copy()
            env["PYTHONPATH"] = f"{self._repo_root}/src:{self._repo_root}"

            proc = await asyncio.create_subprocess_exec(
                "pytest",
                "-c",
                "/dev/null",
                "-p",
                "no:cov",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                "-v",
                str(abs_temp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(self._repo_root),
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

            output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
            ok = proc.returncode == 0

            # Parse output to identify individual test results
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
        finally:
            try:
                self._fh.remove_file(temp_rel_path)
            except Exception:
                pass

    def _parse_test_results(self, output: str) -> tuple[list[str], list[str]]:
        """
        Parse pytest -v output to identify which tests passed/failed.

        Example pytest -v output:
            ../../../dev::test_one PASSED
            test_file.py::test_two FAILED
            test_file.py::TestClass::test_method PASSED
        """
        passed = []
        failed = []

        # Match lines with "::test_name PASSED" or "FAILED"
        # Captures the test name after :: and before the status
        # Handles: path::test_name, path::ClassName::test_name, etc.
        pattern = re.compile(r"::([a-zA-Z_][a-zA-Z0-9_]*)\s+(PASSED|FAILED)")

        for match in pattern.finditer(output):
            test_name = match.group(1)
            status = match.group(2)

            if status == "PASSED":
                passed.append(test_name)
            elif status == "FAILED":
                failed.append(test_name)

        return passed, failed
