# src/mind/logic/engines/registry.py
# ID: b084f16d-e878-465b-84af-72fe10a2ceb1

"""
Dynamic Registry of Governance Engines.
Uses Introspection to discover and initialize engines at runtime.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any, ClassVar

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.llm.client import LLMClient
    from shared.path_resolver import PathResolver

logger = getLogger(__name__)

# Metadata-only engines defined in YAML that should be handled silently
PASSIVE_ALIASES = {
    "python_runtime",
    "type_system",
    "runtime_metric",
    "advisory",
    "runtime_check",
    "dataclass_validation",
}


# ID: f80b6018-9642-4f69-bfcb-d5ab35f7b1d1
class EngineRegistry:
    """
    Dynamic Registry for Governance Engines.
    Automatically discovers engines in the current package.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _engine_classes: ClassVar[dict[str, type]] = {}
    _path_resolver: ClassVar[PathResolver | None] = None
    _llm_client: ClassVar[LLMClient | None] = None
    _discovered: ClassVar[bool] = False

    @classmethod
    # ID: b0cfcefb-27db-4db3-b5e7-754e1d16c958
    def initialize(
        cls, path_resolver: PathResolver, llm_client: LLMClient | None = None
    ) -> None:
        cls._path_resolver = path_resolver
        cls._llm_client = llm_client
        cls._instances.clear()
        cls._discover_engines()
        logger.debug("EngineRegistry primed with dynamic discovery.")

    @classmethod
    def _discover_engines(cls):
        """Scans the engines directory for BaseEngine implementations."""
        if cls._discovered:
            return

        import mind.logic.engines as engines_pkg

        from .base import BaseEngine

        for _, name, _ in pkgutil.iter_modules(engines_pkg.__path__):
            try:
                module = importlib.import_module(
                    f".{name}", package="mind.logic.engines"
                )
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseEngine) and obj is not BaseEngine:
                        eid = getattr(obj, "engine_id", name)
                        cls._engine_classes[eid] = obj
            except Exception as e:
                logger.warning("Failed to load engine module %s: %s", name, e)

        cls._discovered = True

    @classmethod
    # ID: 69a7916b-b8f4-4509-bb2c-897eec528adf
    def get(cls, engine_id: str) -> Any:
        if cls._path_resolver is None:
            raise ValueError("EngineRegistry not initialized.")

        # HEAL: Resolve Passive Aliases to the passive_gate
        target_id = "passive_gate" if engine_id in PASSIVE_ALIASES else engine_id

        if target_id in cls._instances:
            return cls._instances[target_id]

        if target_id not in cls._engine_classes:
            # Re-run discovery just in case
            cls._discover_engines()
            if target_id not in cls._engine_classes:
                raise ValueError(f"Unsupported Governance Engine: {engine_id}")

        engine_cls = cls._engine_classes[target_id]

        # JIT Initialization with Smart Injection
        # We check the constructor to see what dependencies the engine actually wants.
        sig = inspect.signature(engine_cls.__init__)
        params = {}

        if "path_resolver" in sig.parameters:
            params["path_resolver"] = cls._path_resolver

        if "llm_client" in sig.parameters:
            # Provide stub if real client is missing
            if cls._llm_client:
                params["llm_client"] = cls._llm_client
            else:
                from .llm_gate_stub import LLMGateStubEngine

                logger.debug("Redirecting %s to Stub (No LLM Client)", target_id)
                return LLMGateStubEngine()

        cls._instances[target_id] = engine_cls(**params)
        return cls._instances[target_id]
