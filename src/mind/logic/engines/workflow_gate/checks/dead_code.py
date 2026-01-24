# src/mind/logic/engines/workflow_gate/checks/dead_code.py

"""Refactored logic for src/mind/logic/engines/workflow_gate/checks/dead_code.py."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.path_resolver import PathResolver


# ID: 6b4cf33a-4fe2-4c5d-9af5-9009d9a52ef8
class DeadCodeCheck(WorkflowCheck):
    """
    Verifies that the codebase is free of dead code using Vulture.
    """

    check_type = "dead_code_check"

    def __init__(self, path_resolver: PathResolver) -> None:
        self._paths = path_resolver

    # ID: 69ab4e1f-14af-467b-8fd1-4e4e14ca0e96
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        # If a specific file is provided, check only that, otherwise check src/
        target = str(file_path) if file_path else "src/"
        confidence = params.get("confidence", 80)

        violations = []
        try:
            # We run vulture as a subprocess to keep the 'Body' lean
            cmd = ["vulture", target, "--min-confidence", str(confidence)]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._paths.repo_root),
            )
            stdout, _ = await process.communicate()

            output = stdout.decode().strip()
            if output:
                # We turn the tool's output into a 'Judicial Finding'
                for line in output.splitlines():
                    violations.append(f"Dead code detected: {line}")

        except Exception as e:
            violations.append(f"Dead code analysis failed: {e}")

        return violations
