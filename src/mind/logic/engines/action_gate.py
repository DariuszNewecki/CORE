# src/mind/logic/engines/action_gate.py

"""Provides functionality for the action_gate module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult


# ID: 480ac80d-4928-4408-ad9b-f4d77f1b3b25
class ActionGateEngine(BaseEngine):
    """
    Operation Intent Auditor.
    Enforces governance based on the TYPE of action being performed (e.g., 'schema_migration').
    """

    engine_id = "action_gate"

    # ID: cc81843f-33db-479a-9c5c-52d90e14134f
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        violations = []

        # FACT: The Auditor must provide the 'action_id' being attempted.
        # This usually comes from the @atomic_action decorator or the Agent Task.
        attempted_action = params.get("attempted_action")
        if not attempted_action:
            return EngineResult(
                ok=False,
                message="Governance Error: No attempted_action provided to ActionGate.",
                violations=["Internal: Action ID missing in context"],
                engine_id=self.engine_id,
            )

        # 1. Fact: Check Prohibited Actions (Blacklist)
        prohibited = params.get("actions_prohibited", [])
        if attempted_action in prohibited:
            require_type = params.get("require", "human_approval")
            violations.append(
                f"Action '{attempted_action}' is PROHIBITED autonomously. (Requires: {require_type})"
            )

        # 2. Fact: Check Allowed Actions (Whitelist / Scope restriction)
        allowed = params.get("actions_allowed")
        if allowed is not None:  # If a whitelist is explicitly defined
            if attempted_action not in allowed:
                violations.append(
                    f"Action '{attempted_action}' is outside the permitted scope for this principle."
                )

        if not violations:
            return EngineResult(
                ok=True,
                message=f"Action '{attempted_action}' authorized by policy.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message="Constitutional Block: Unauthorized Operation Intent.",
            violations=violations,
            engine_id=self.engine_id,
        )
