# src/mind/logic/engines/passive_gate.py
# ID: c2bd0af2-60d8-414e-a6ca-f36ac1a0d5d2

"""
Passive Gate Engine - Constitutional Metadata Handler.

Used for rules that are enforced by the system substrate (Python runtime,
type system, or hardcoded logic) rather than a dynamic checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult


# ID: 8f3431f3-5ede-4088-a279-d0c1cab89f28
class PassiveGateEngine(BaseEngine):
    """
    A "Silent" engine that always returns OK.

    Used to satisfy the Auditor when a rule documents an
    internal system constraint (e.g. engine: type_system).
    """

    engine_id = "passive_gate"

    # ID: 2f24dd30-e6d6-4d2e-8e8f-1081a48ca85f
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Always returns OK.
        The rule is enforced by the substrate, not this engine.
        """
        return EngineResult(
            ok=True,
            message="Internal enforcement acknowledged.",
            violations=[],
            engine_id=self.engine_id,
        )

    # ID: 2d88b899-48d5-49b6-8122-86f06703924a
    async def verify_context(self, context: Any, params: dict[str, Any]) -> list:
        """Context-level version for the dynamic auditor."""
        return []
