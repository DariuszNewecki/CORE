# src/mind/logic/engines/registry.py

"""
Registry of Governance Engines.
Uses Deferred Resolution and explicit initialization to prevent circular imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from shared.logger import getLogger


if TYPE_CHECKING:
    # CONSTITUTIONAL FIX: Import from shared, not body
    from shared.infrastructure.llm.client import LLMClient
    from shared.path_resolver import PathResolver

logger = getLogger(__name__)


# ID: b084f16d-e878-465b-84af-72fe10a2ceb1
class EngineRegistry:
    """
    Registry of Governance Engines.
    Acts as a Static Singleton Service Locator.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _path_resolver: ClassVar[PathResolver | None] = None
    _llm_client: ClassVar[LLMClient | None] = None

    @classmethod
    # ID: 7dd9acaf-b2ce-44d3-9037-6d1256afd0a0
    def initialize(
        cls, path_resolver: PathResolver, llm_client: LLMClient | None = None
    ) -> None:
        """
        Prime the registry with infrastructure dependencies.
        Must be called by the ConstitutionalAuditor or System Bootstrap.
        """
        cls._path_resolver = path_resolver
        cls._llm_client = llm_client
        # Clear instances to ensure they are re-created with new deps if re-initialized
        cls._instances.clear()
        logger.debug(
            "EngineRegistry primed (intent_root=%s)", path_resolver.intent_root
        )

    @classmethod
    # ID: ca1802fd-03b9-47a1-8093-851947afde4c
    def get(cls, engine_id: str) -> Any:
        """
        Retrieves or initializes the requested engine.
        Raises ValueError if registry hasn't been initialized with PathResolver.
        """
        if cls._path_resolver is None:
            raise ValueError(
                "EngineRegistry not initialized. "
                "Call EngineRegistry.initialize(path_resolver) first."
            )

        if engine_id in cls._instances:
            return cls._instances[engine_id]

        logger.debug("Lazy-loading engine: %s", engine_id)

        if engine_id == "ast_gate":
            from .ast_gate import ASTGateEngine

            # CONSTITUTIONAL FIX: Pass path_resolver to ASTGateEngine
            cls._instances[engine_id] = ASTGateEngine(cls._path_resolver)

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

            # CONSTITUTIONAL FIX: Pass path_resolver to WorkflowGateEngine
            cls._instances[engine_id] = WorkflowGateEngine(cls._path_resolver)

        elif engine_id == "knowledge_gate":
            from .knowledge_gate import KnowledgeGateEngine

            cls._instances[engine_id] = KnowledgeGateEngine()

        elif engine_id == "llm_gate":
            # Handle Stub vs Real LLM based on injection
            if cls._llm_client:
                from .llm_gate import LLMGateEngine

                cls._instances[engine_id] = LLMGateEngine(cls._llm_client)
            else:
                from .llm_gate_stub import LLMGateStubEngine

                cls._instances[engine_id] = LLMGateStubEngine()
        else:
            raise ValueError(f"Unsupported Governance Engine: {engine_id}")

        return cls._instances[engine_id]
