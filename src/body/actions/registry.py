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


# ID: 9b377117-5527-49cb-ae3f-da4e4375e859
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
                    f"Duplicate action name '{instance.name}' found. Overwriting."
                )
            self._handlers[instance.name] = instance
        logger.info(f"ActionRegistry initialized with {len(self._handlers)} handlers.")

    # ID: 02099ee5-6534-49ba-be58-408d43f86f77
    def get_handler(self, action_name: str) -> ActionHandler | None:
        """Retrieves a handler instance by its action name."""
        return self._handlers.get(action_name)
