# src/mind/logic/engines/workflow_gate/checks/tests.py

"""
Test verification workflow check.

Verifies that the most recent test suite execution passed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
class TestVerificationCheck(WorkflowCheck):
    """
    Checks if the most recent test workflow passed.

    Queries action_results database table for test execution outcomes.
    """

    check_type = "test_verification"

    # ID: b17085a1-d0f0-4a10-9e2a-801372462e81
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify tests passed.

        Args:
            file_path: Unused (context-level check)
            params: Check parameters (currently unused)

        Returns:
            List of violations if tests failed or not found
        """
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT ok, error_message
                    FROM core.action_results
                    WHERE action_type = 'test_execution'
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                )
            )
            row = result.fetchone()

            if not row:
                return [
                    "No test execution history found. Tests must be run before integration."
                ]

            if not row[0]:  # ok = False
                error = row[1] or "Unknown test failure"
                return [f"Required test suite failed: {error}"]

            return []
