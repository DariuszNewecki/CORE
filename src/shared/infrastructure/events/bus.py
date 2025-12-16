# src/shared/infrastructure/events/bus.py
# ID: infra.events.bus
"""
In-Memory Event Bus.
Provides a singleton mechanism for decoupling components via events.
"""

from __future__ import annotations

from collections.abc import Callable

from shared.logger import getLogger

from .base import CloudEvent


logger = getLogger(__name__)

EventHandler = Callable[[CloudEvent], None]


# ID: d96a395b-da60-459d-8b40-76a5806f9cdd
class EventBus:
    """
    Synchronous In-Memory Event Bus.
    """

    _instance: EventBus | None = None
    _subscribers: dict[str, list[EventHandler]] = {}

    @classmethod
    # ID: 50193784-7898-4bfc-9f4b-5daaf58ea9a1
    def get_instance(cls) -> EventBus:
        """Get the singleton instance of the EventBus."""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    # ID: efad6590-574d-418b-821c-5ec932d5736f
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Register a handler for a specific event type.
        Use '*' for wildcard subscription (all events).
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed handler to event type: %s", event_type)

    # ID: 5fb18622-b0a0-4f86-ac8b-207036292e4a
    def emit(self, event: CloudEvent) -> None:
        """
        Emit an event to all subscribers of its type.
        Also triggers wildcard '*' subscribers.
        """
        handlers = self._subscribers.get(event.type, [])
        # Also support wildcard subscriptions '*'
        handlers.extend(self._subscribers.get("*", []))

        if not handlers:
            logger.debug("No handlers for event: %s", event.type)
            return

        logger.debug("Emitting event: %s to %d handlers", event.type, len(handlers))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # We do not crash the bus; observability picks this up via logs
                logger.error(
                    "Error in event handler for %s: %s",
                    event.type,
                    str(e),
                    exc_info=True,
                )
