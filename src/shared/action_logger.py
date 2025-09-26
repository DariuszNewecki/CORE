# src/shared/action_logger.py
"""
Provides a dedicated service for writing structured, auditable events to the system's action log.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from shared.config import settings
from shared.logger import getLogger

log = getLogger("action_logger")


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class ActionLogger:
    """Handles writing structured JSON events to the CORE_ACTION_LOG_PATH."""

    def __init__(self):
        """Initializes the logger, ensuring the log file's parent directory exists."""
        try:
            log_path_str = settings.CORE_ACTION_LOG_PATH
            if not log_path_str:
                raise ValueError("CORE_ACTION_LOG_PATH is not set in the environment.")
            self.log_path = settings.REPO_PATH / log_path_str
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        except (ValueError, AttributeError) as e:
            log.error(
                f"ActionLogger failed to initialize: {e}. Logging will be disabled."
            )
            self.log_path = None

    # ID: 5d7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
    def log_event(self, event_type: str, details: Dict[str, Any]):
        """
        Writes a single, timestamped event to the action log file.

        Args:
            event_type: A dot-notation string identifying the event (e.g., 'crate.processing.started').
            details: A dictionary of context-specific information about the event.
        """
        if not self.log_path:
            return  # Fail silently if the logger could not be initialized.

        log_entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            log.error(f"Failed to write to action log at {self.log_path}: {e}")


# A singleton instance for easy access across the application
action_logger = ActionLogger()
