# src/mind/logic/engines/workflow_gate/checks/tests.py
# ID: 1480ffd7-6c3e-46a9-b331-de8c33790349

"""
Test verification workflow check.

Verifies that the most recent test suite execution passed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 33057f65-4f93-452d-a3cd-2a073147dae8
class TestVerificationCheck(WorkflowCheck):
    """
    Checks if the most recent test workflow passed by querying the Action Ledger.
    """

    check_type = "test_verification"

    # ID: b17085a1-d0f0-4a10-9e2a-801372462e81
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify tests passed using the database session provided in params.

        Args:
            file_path: Unused (context-level check)
            params: Must contain '_context' with an active 'db_session'
        """
        context = params.get("_context")
        session = getattr(context, "db_session", None)

        if not session:
            logger.warning(
                "TestVerificationCheck: Database session unavailable in context."
            )
            # We report a sensory gap if the execution environment didn't provide a session.
            return ["System Sensation Error: Action Ledger (DB) is unreachable."]

        try:
            # 1. Query the Mind's memory (Postgres SSOT) for the last test result
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

            # 2. Logic Evaluation
            if not row:
                return [
                    "No test execution history found. The test suite MUST be "
                    "executed before this workflow can proceed."
                ]

            if not row[0]:  # row['ok'] == False
                error = row[1] or "Unknown test failure"
                return [f"Required test suite failed: {error}"]

            # SUCCESS: No violations found
            return []

        except Exception as e:
            logger.error("Failed to query test results: %s", e)
            return [f"Database Query Error: {e}"]
