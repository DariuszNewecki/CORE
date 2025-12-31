# src/mind/logic/engines/registry.py
# ID: 8bac9905-e646-4204-aba1-20b5f51b209e

"""
Registry of Governance Engines.
Refactored to use Lazy-Loading to prevent circular imports during system bootstrap.
"""

from __future__ import annotations

from typing import Any, ClassVar

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 8bac9905-e646-4204-aba1-20b5f51b209e
class EngineRegistry:
    """
    Registry of Governance Engines.
    Uses Deferred Resolution to prevent circular initialization loops.
    """

    _instances: ClassVar[dict[str, Any]] = {}

    @classmethod
    # ID: ca1802fd-03b9-47a1-8093-851947afde4c
    def get(cls, engine_id: str) -> Any:
        """Retrieves or initializes the requested engine with lazy loading."""
        if engine_id in cls._instances:
            return cls._instances[engine_id]

        logger.debug("Lazy-loading engine: %s", engine_id)

        if engine_id == "ast_gate":
            from .ast_gate import ASTGateEngine

            cls._instances[engine_id] = ASTGateEngine()
        elif engine_id == "glob_gate":
            from .glob_gate import GlobGateEngine

            cls._instances[engine_id] = GlobGateEngine()
        elif engine_id == "action_gate":
            from .action_gate import ActionGateEngine

            cls._instances[engine_id] = ActionGateEngine()
        elif engine_id == "regex_gate":
            from .regex_gate import RegexGateEngine

            cls._instances[engine_id] = RegexGateEngine()
        elif engine_id == "workflow_gate":
            from .workflow_gate import WorkflowGateEngine

            cls._instances[engine_id] = WorkflowGateEngine()
        elif engine_id == "knowledge_gate":
            from .knowledge_gate import KnowledgeGateEngine

            cls._instances[engine_id] = KnowledgeGateEngine()
        elif engine_id == "llm_gate":
            # Handle Stub vs Real LLM
            if hasattr(settings, "LLM_API_URL") and settings.LLM_API_URL:
                from .llm_gate import LLMGateEngine

                cls._instances[engine_id] = LLMGateEngine()
            else:
                from .llm_gate_stub import LLMGateStubEngine

                cls._instances[engine_id] = LLMGateStubEngine()
        else:
            raise ValueError(f"Unsupported Governance Engine: {engine_id}")

        return cls._instances[engine_id]
