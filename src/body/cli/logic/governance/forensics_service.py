# src/body/cli/logic/governance/forensics_service.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567898

"""
Forensics Service - Phase 3 Hardening.
Reconstructs the Chain of Legality by linking Agent decisions to Body actions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from body.services.service_registry import service_registry
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f1a2b3c4-d5e6-7890-abcd-ef1234567890
class GovernanceForensicsService:
    """
    Assembles evidence packets for autonomous operations.
    """

    def __init__(self):
        self.session_factory = service_registry.session

    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    async def get_audit_trail(self, session_id: str) -> dict[str, Any]:
        """
        Retrieves the complete history of thoughts and actions for a session.
        """
        async with self.session_factory() as session:
            # 1. Get the Agent's reasoning (The Intent)
            trace_query = text(
                """
                SELECT agent_name, goal, decisions, pattern_stats
                FROM core.decision_traces
                WHERE session_id = :sid
            """
            )
            trace_res = await session.execute(trace_query, {"sid": session_id})
            trace = trace_res.mappings().first()

            # 2. Get the Body's execution (The Action)
            # We match by looking for the session_id in the action metadata
            action_query = text(
                """
                SELECT action_type, ok, error_message, action_metadata, created_at
                FROM core.action_results
                WHERE action_metadata::text LIKE :sid_pattern
                ORDER BY created_at ASC
            """
            )
            action_res = await session.execute(
                action_query, {"sid_pattern": f"%{session_id}%"}
            )
            actions = action_res.mappings().all()

        return {
            "session_id": session_id,
            "intent": dict(trace) if trace else None,
            "actions": [dict(a) for a in actions],
            "legality_verified": trace is not None and len(actions) > 0,
        }
