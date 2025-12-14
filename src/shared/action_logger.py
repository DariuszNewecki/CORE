# src/shared/action_logger.py

"""
Provides a dedicated service for writing structured, auditable events to the system's action log.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 72f18eea-652f-4098-8ddd-211a346c95fd
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
            logger.error(
                "ActionLogger failed to initialize: %s. Logging will be disabled.", e
            )
            self.log_path = None

    # ID: 45f05bd1-dc47-4dfc-9117-709dff10741e
    def log_event(self, event_type: str, details: dict[str, Any]):
        """
        Writes a single, timestamped event to the action log file.

        Args:
            event_type: A dot-notation string identifying the event (e.g., 'crate.processing.started').
            details: A dictionary of context-specific information about the event.
        """
        if not self.log_path:
            return
        log_entry = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error("Failed to write to action log at {self.log_path}: %s", e)


action_logger = ActionLogger()
