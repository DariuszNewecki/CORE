# src/shared/infrastructure/events/base.py
# ID: infra.events.base
"""
CloudEvents-compliant Event Envelope.
Defines the standard data structure for all system events.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
# ID: c36129bc-c9b2-477a-91df-56cdb8281deb
class CloudEvent:
    """
    Standard CloudEvent envelope v1.0.
    See .intent/standards/architecture/event_schema_standard.json
    """

    type: str  # e.g., 'core.governance.violation'
    source: str  # e.g., 'service:intent_guard'
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    time: datetime = field(default_factory=lambda: datetime.now(UTC))
    specversion: str = "1.0"
    datacontenttype: str = "application/json"
    subject: str | None = None

    # ID: 9eb436d7-adbd-448a-8329-1577e568c9e9
    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary."""
        return {
            "specversion": self.specversion,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "time": self.time.isoformat(),
            "datacontenttype": self.datacontenttype,
            "data": self.data,
            "subject": self.subject,
        }
