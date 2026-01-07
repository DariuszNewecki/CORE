# src/features/test_generation_v2/sandbox.py
"""
Pytest Sandbox Runner

Purpose:
- Execute generated tests in isolation.
- Return a scoring signal (passed/failed) plus failure evidence.

Constitutional Fix (already present in your project):
- -c /dev/null ignores repo pytest config.
- -p no:cov disables coverage plugin in sandbox.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from shared.infrastructure.storage.file_handler import FileHandler


@dataclass(frozen=True)
# ID: e5e9db6a-3e15-4f9d-9d86-c2c77ff09c8a
class SandboxResult:
    passed: bool
    error: str = ""


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
                    passed=False, error=f"Execution timeout ({timeout_seconds}s)."
                )

            output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
            ok = proc.returncode == 0
            return SandboxResult(passed=ok, error=("" if ok else output))

        except Exception as e:
            return SandboxResult(passed=False, error=str(e))
        finally:
            try:
                self._fh.remove_file(temp_rel_path)
            except Exception:
                pass
