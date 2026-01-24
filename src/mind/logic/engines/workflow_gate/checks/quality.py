# src/mind/logic/engines/workflow_gate/checks/quality.py

"""Refactored logic for src/mind/logic/engines/workflow_gate/checks/quality.py."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.path_resolver import PathResolver


# ID: e56a1a25-9a1e-4938-b6fa-34f7263be922
class QualityGateCheck(WorkflowCheck):
    """Universal wrapper for external industrial quality tools."""

    def __init__(self, path_resolver: PathResolver, check_type: str, cmd: list[str]):
        self._paths = path_resolver
        self.check_type = check_type
        self.cmd = cmd

    # ID: 27f1838d-001f-4f3e-aea9-7c651fea7a62
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        try:
            # We reuse the logic from your quality_gates script
            process = await asyncio.create_subprocess_exec(
                *self.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._paths.repo_root),
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

            if process.returncode != 0:
                output = stdout.decode().strip() or stderr.decode().strip()
                # We return the FIRST line of the error to keep the report clean
                error_msg = output.split("\n")[0]
                return [f"Quality Gate {self.check_type} failed: {error_msg}"]
        except Exception as e:
            return [f"Gate {self.check_type} error: {e!s}"]
        return []
