# src/core/actions/registry.py
"""
A registry for discovering and accessing all available ActionHandlers.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

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


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e
# ID: 2063313d-3cd6-4732-956b-e0b9fc7a5924
class ActionRegistry:
    """A central registry for all action handlers."""

    def __init__(self):
        self._handlers: Dict[str, ActionHandler] = {}
        self._register_handlers()

    def _register_handlers(self):
        """Discovers and registers all concrete ActionHandler classes."""
        handlers_to_register: List[Type[ActionHandler]] = [
            ReadFileHandler,
            ListFilesHandler,
            DeleteFileHandler,
            CreateFileHandler,
            EditFileHandler,
            CreateProposalHandler,
            EditFunctionHandler,
            # Add our new handlers to the list
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
    def get_handler(self, action_name: str) -> Optional[ActionHandler]:
        """Retrieves a handler instance by its action name."""
        return self._handlers.get(action_name)
