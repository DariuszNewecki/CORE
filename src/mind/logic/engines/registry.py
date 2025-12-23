# src/mind/logic/engines/registry.py

"""Provides functionality for the registry module."""

from __future__ import annotations

from typing import ClassVar

from .action_gate import ActionGateEngine
from .ast_gate import ASTGateEngine
from .base import BaseEngine
from .glob_gate import GlobGateEngine
from .llm_gate import LLMGateEngine
from .regex_gate import RegexGateEngine
from .workflow_gate import WorkflowGateEngine


# ID: 8bac9905-e646-4204-aba1-20b5f51b209e
class EngineRegistry:
    """
    Registry of Governance Engines.
    Uses Lazy-Loading to prevent configuration crashes on import.
    """

    _engine_classes: ClassVar[dict[str, type[BaseEngine]]] = {
        "ast_gate": ASTGateEngine,
        "glob_gate": GlobGateEngine,
        "action_gate": ActionGateEngine,
        "regex_gate": RegexGateEngine,
        "workflow_gate": WorkflowGateEngine,
        "llm_gate": LLMGateEngine,
    }

    _instances: ClassVar[dict[str, BaseEngine]] = {}

    @classmethod
    # ID: a14c94f2-1006-4267-a626-54d9ffec9b1a
    def get(cls, engine_id: str) -> BaseEngine:
        """Retrieves or initializes the requested engine."""
        if engine_id not in cls._engine_classes:
            raise ValueError(f"Unsupported Governance Engine: {engine_id}")

        if engine_id not in cls._instances:
            # Instantiate on demand
            engine_class = cls._engine_classes[engine_id]
            cls._instances[engine_id] = engine_class()

        return cls._instances[engine_id]
