# src/features/self_healing/alignment/sandbox.py

"""Refactored logic for src/features/self_healing/alignment/sandbox.py."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from shared.config import settings


# ID: 561ad23f-b5dd-4bf2-b1e1-c9c966de110e
async def verify_import_safety(file_path: str) -> tuple[bool, str]:
    """Sandbox test to ensure the file is 'compilable'."""
    module_path = file_path.replace("src/", "").replace(".py", "").replace("/", ".")
    check_code = f"import {module_path}\nprint('ALIVE')"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(check_code)
        temp_path = f.name

    try:
        src_path = str((settings.REPO_PATH / "src").resolve())
        proc = await asyncio.create_subprocess_exec(
            "env",
            f"PYTHONPATH={src_path}",
            "python3",
            temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(settings.REPO_PATH),
        )
        _, stderr = await proc.communicate()
        return (proc.returncode == 0, stderr.decode("utf-8"))
    finally:
        await asyncio.to_thread(Path(temp_path).unlink, missing_ok=True)
