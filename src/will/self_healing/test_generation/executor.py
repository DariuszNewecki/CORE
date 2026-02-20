# src/features/self_healing/test_generation/executor.py
"""
TestExecutor - runs pytest, returns structured results.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from body.services.file_service import FileService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 4c3f5ca8-a00d-47c8-adc8-a82c10c77afb
class TestExecutor:
    """Responsible for writing and executing tests."""

    # ID: 8bcc90c1-35c2-47f2-abeb-ea80d6243cf9
    async def execute_test(
        self,
        test_file: str,
        code: str,
        file_handler: FileService,
        repo_root: Path,
    ) -> dict:
        # Ensure parent directory exists via governed channel
        path = repo_root / test_file
        parent_rel = str(path.parent.relative_to(repo_root))
        file_handler.ensure_dir(parent_rel)

        # Write test file via governed channel
        result = file_handler.write_runtime_text(test_file, code)
        if result.status != "success":
            raise RuntimeError(f"Governance rejected write: {result.message}")

        try:
            process = await asyncio.create_subprocess_exec(
                "pytest",
                str(path),
                "-v",
                "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_root,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        except Exception as e:
            return {"status": "failed", "error": str(e)}

        return {
            "status": "success" if process.returncode == 0 else "failed",
            "output": stdout.decode(),
            "errors": stderr.decode(),
            "returncode": process.returncode,
        }
