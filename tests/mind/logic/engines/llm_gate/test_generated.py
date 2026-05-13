# src/mind/logic/engines/llm_gate.py

from src.mind.logic.engines.base_engine import BaseEngine, EngineResult

class LLMGateStubEngine(BaseEngine):
    """
    Stub LLM Gate - always passes, no API calls.

    This is a placeholder that allows the audit system to run
    without requiring LLM API configuration or incurring costs.
    """

    engine_id = "llm_gate_stub"

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Stub verification - always returns OK.

        Natively async to match the BaseEngine signature.
        """
        return EngineResult(
            ok=True,
            message="Verification passed (stub)",
            engine_id=self.engine_id,
        )
