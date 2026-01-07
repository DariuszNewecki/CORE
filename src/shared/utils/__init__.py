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


# ID: ca71dd28-0aff-45c8-bba2-f4d12e7bcb7c
def create_greeting_action(names: list[str], *, write: bool = False) -> list[str]:
    """
    Action pattern for creating multiple greetings.
    """
    if not isinstance(names, list):
        raise TypeError("names must be a list")

    greetings = []
    try:
        for name in names:
            if not isinstance(name, str):
                raise TypeError(f"All names must be strings. Found: {type(name)}")
            greetings.append(create_greeting(name))

        if write:
            pass
        return greetings

    except Exception as e:
        raise


# ID: d8b9f0cb-037b-47ed-b0c2-b280b1d15ad2
def format_greeting_for_output(greeting: str, style: str = "standard") -> str:
    """
    Format a greeting for different output styles.
    """
    styles: dict[str, Callable[[str], str]] = {
        "standard": lambda g: g,
        "uppercase": lambda g: g.upper(),
        "lowercase": lambda g: g.lower(),
        "excited": lambda g: g.replace("!", "!!!") if "!" in g else g + "!!!",
    }

    formatter = styles.get(style, styles["standard"])
    # FIXED: Added cast to str for MyPy
    return cast(str, formatter(greeting))
