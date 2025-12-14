# src/body/actions/registry.py

"""
A registry for discovering and accessing all available ActionHandlers.
"""

from __future__ import annotations

from shared.logger import getLogger

from .base import ActionHandler
from .code_actions import CreateFileHandler, EditFileHandler, EditFunctionHandler
from .file_actions import DeleteFileHandler, ListFilesHandler, ReadFileHandler
from .governance_actions import CreateProposalHandler
from .healing_actions import FixDocstringsHandler, FixHeadersHandler, FormatCodeHandler
from .healing_actions_extended import (
    AddPolicyIDsHandler,
    EnforceLineLengthHandler,
    FixUnusedImportsHandler,
    RemoveDeadCodeHandler,
    SortImportsHandler,
)
from .validation_actions import ValidateCodeHandler


logger = getLogger(__name__)


# ID: cfe2b329-83f6-4bb8-8a17-eef2886864b8
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
            FixUnusedImportsHandler,
            RemoveDeadCodeHandler,
            EnforceLineLengthHandler,
            AddPolicyIDsHandler,
            SortImportsHandler,
        ]
        for handler_class in handlers_to_register:
            instance = handler_class()
            if instance.name in self._handlers:
                logger.warning(
                    "Duplicate action name '%s' found. Overwriting.", instance.name
                )
            self._handlers[instance.name] = instance
        logger.info("ActionRegistry initialized with %s handlers.", len(self._handlers))

    # ID: deeeec9e-e8d4-423c-b88f-990fc63521a8
    def get_handler(self, action_name: str) -> ActionHandler | None:
        """Retrieves a handler instance by its action name."""
        return self._handlers.get(action_name)
