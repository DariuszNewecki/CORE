# src/mind/logic/engines/workflow_gate/checks/dead_code.py

"""Dead-code check — delegates subprocess execution to the shared sanctuary.

Issue #585: subprocess invocation was previously inline in this Mind-layer
file (asyncio.create_subprocess_exec on vulture). That placed execution
semantics inside Mind in violation of architecture.layers.no_mind_execution.
The vulture invocation now lives at shared.utils.subprocess_utils.run_vulture
— the canonical subprocess sanctuary — and this module reads the structured
result and turns it into findings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import run_vulture


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

        violations: list[str] = []
        try:
            result = await run_vulture(
                target=target,
                repo_root=self._paths.repo_root,
                confidence=confidence,
            )
            output = result.stdout.strip()
            if output:
                for line in output.splitlines():
                    violations.append(f"Dead code detected: {line}")
        except Exception as e:
            violations.append(f"Dead code analysis failed: {e}")

        return violations
