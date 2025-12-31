# src/mind/logic/engines/workflow_gate/checks/canary.py

"""
Canary deployment workflow check.

Ensures a canary deployment passed in a protected environment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f6a7b8c9-d0e1-2f3a-4b5c-6d7e8f9a0b1c
class CanaryDeploymentCheck(WorkflowCheck):
    """
    Ensures a canary deployment passed in a protected environment.

    Simple boolean check from params.
    """

    check_type = "canary_audit"

    # ID: 5e141bf2-5f4d-4c6c-b8df-2392506af91f
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify canary deployment passed.

        Args:
            file_path: Unused
            params: Must include 'canary_passed' boolean

        Returns:
            List with violation if canary didn't pass
        """
        if not params.get("canary_passed", False):
            return [
                "Canary audit required: Operation must pass in staging/isolation first."
            ]
        return []
