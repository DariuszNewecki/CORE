# src/shared/utils/__init__.py

"""
Shared utility functions and helpers.

Pure, stateless functions with no side effects.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import cast


# ID: fca84726-8bb7-4472-80cf-9d847144a1b2
def create_greeting(name: str, *, time_of_day: str | None = None) -> str:
    """
    Create a personalized greeting message.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Name must be a non-empty string")

    if time_of_day is None:
        current_hour = datetime.now().hour
        if current_hour < 12:
            time_of_day = "morning"
        elif current_hour < 17:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"

    time_greetings = {
        "morning": "Good morning",
        "afternoon": "Good afternoon",
        "evening": "Good evening",
        "night": "Good night",
    }

    base_greeting = time_greetings.get(time_of_day.lower(), "Hello")
    return f"{base_greeting}, {name}!"
