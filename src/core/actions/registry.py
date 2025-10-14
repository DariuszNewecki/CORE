# src/core/actions/registry.py
"""
A registry for discovering and accessing all available ActionHandlers.
"""

from __future__ import annotations

from shared.logger import getLogger

from .base import ActionHandler
from .code_actions import CreateFileHandler, EditFileHandler, EditFunctionHandler
from .file_actions import DeleteFileHandler, ListFilesHandler, ReadFileHandler
from .governance_actions import CreateProposalHandler
from .healing_actions import (
    FixDocstringsHandler,
    FixHeadersHandler,
    FormatCodeHandler,
)
from .validation_actions import ValidateCodeHandler

log = getLogger("action_registry")


# ID: b351ac04-4574-409e-a4ad-90a1e8225947
class ActionRegistry:
    """A central registry for all action handlers."""

    def __init__(self):
        self._handlers: dict[str, ActionHandler] = {}
        self._register_handlers()

    def _register_handlers(self):
        """Discovers and registers all concrete ActionHandler classes."""
        handlers_to_register: list[type[ActionHandler]] = [
            ReadFileHandler,
            ListFilesHandler,
            DeleteFileHandler,
            CreateFileHandler,
            EditFileHandler,
            CreateProposalHandler,
            EditFunctionHandler,
            FixHeadersHandler,
            FixDocstringsHandler,
            FormatCodeHandler,
            ValidateCodeHandler,
        ]

        for handler_class in handlers_to_register:
            instance = handler_class()
            if instance.name in self._handlers:
                log.warning(
                    f"Duplicate action name '{instance.name}' found. Overwriting."
                )
            self._handlers[instance.name] = instance
        log.info(f"ActionRegistry initialized with {len(self._handlers)} handlers.")

    # ID: c1cf8df7-795d-44a0-92f3-2e7f8b99455d
    def get_handler(self, action_name: str) -> ActionHandler | None:
        """Retrieves a handler instance by its action name."""
        return self._handlers.get(action_name)
