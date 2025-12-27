# src/mind/logic/engines/llm_gate_stub.py
"""
Stub LLM Gate Engine - No-op implementation for testing.

This engine replaces the real LLM gate when LLM API access is not configured.
It allows dynamic rule execution to proceed without API calls or costs.

Behavior:
- Always returns OK (no violations)
- Logs what it would have checked
- Saves money during development
- Can be replaced with real LLM gate later

Usage:
This engine is automatically used when Settings doesn't have LLM_API_URL configured.
See llm_gate.py for the detection logic.

Ref: Dynamic Rule Execution - Phase 1 POC
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.logic.engines.base import BaseEngine, EngineResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: d8f3e9c7-5a2b-4e1f-9d8c-7b6a3e5f2c4d
class LLMGateStubEngine(BaseEngine):
    """
    Stub LLM Gate - always passes, no API calls.

    This is a placeholder that allows the audit system to run
    without requiring LLM API configuration or incurring costs.

    In production, replace this with real LLMGateEngine when
    you want actual LLM-based verification.
    """

    engine_id = "llm_gate"

    def __init__(self):
        """Initialize stub engine - no LLM client needed."""
        logger.info(
            "LLMGateStubEngine initialized - LLM checks will be skipped "
            "(no API calls, no cost)"
        )

    # ID: e9f4d8c7-6b3a-5e2f-8d9c-7a6b4e3f1c2d
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Stub verification - always returns OK.

        Args:
            file_path: File to verify (ignored)
            params: Check parameters including 'instruction' (logged but not executed)

        Returns:
            EngineResult with ok=True (always passes)
        """
        # Log what we would have checked (for debugging)
        instruction = params.get("instruction", "")
        if instruction:
            logger.debug(
                "LLMGateStub: Would check '%s' with instruction: %s",
                file_path.name,
                instruction[:100],
            )

        # Always pass - no violations
        return EngineResult(
            ok=True,
            message="LLM check skipped (stub mode - no API call)",
            violations=[],
            engine_id=self.engine_id,
        )
