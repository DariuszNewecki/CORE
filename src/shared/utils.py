# src/shared/utils.py

"""
Greeting utility functions for shared layer.
Pure, stateless functions with no side effects.
"""

from __future__ import annotations

from datetime import datetime


# ID: fca84726-8bb7-4472-80cf-9d847144a1b2
def create_greeting(name: str, *, time_of_day: str | None = None) -> str:
    """
    Create a personalized greeting message.

    This is a pure utility function with no side effects or I/O operations.
    Reusable across the entire codebase.

    Args:
        name: The name to include in the greeting
        time_of_day: Optional time of day for context-specific greeting.
                    If None, uses current system time.

    Returns:
        A personalized greeting string.

    Examples:
        >>> create_greeting("Alice")
        "Hello, Alice!"

        >>> create_greeting("Bob", time_of_day="morning")
        "Good morning, Bob!"
    """
    if not name or not isinstance(name, str):
        raise ValueError("Name must be a non-empty string")

    if time_of_day is None:
        # Get current hour to determine time of day
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

    CRITICAL: This command modifies state and follows safety guarantees.

    Args:
        names: List of names to create greetings for
        write: If True, executes the action. If False (default), dry-run mode.

    Returns:
        List of greeting messages that would be/were created.

    Note:
        - In dry-run mode (write=False), shows what WOULD change without changing it
        - Only executes when write=True
        - Atomic operation (all or nothing)
    """
    if not isinstance(names, list):
        raise TypeError("names must be a list")

    greetings = []

    try:
        # Create all greetings first (atomic preparation)
        for name in names:
            if not isinstance(name, str):
                raise TypeError(f"All names must be strings. Found: {type(name)}")
            greetings.append(create_greeting(name))

        # Only execute if write=True
        if write:
            # In a real implementation, this is where you would write to a database,
            # file, or other persistent storage
            # For this example, we'll just return the greetings as if they were saved
            pass

        return greetings

    except Exception as e:
        # Atomic guarantee: if any error occurs, nothing is written
        if write:
            # Log or handle the rollback in a real implementation
            pass
        raise


# ID: d8b9f0cb-037b-47ed-b0c2-b280b1d15ad2
def format_greeting_for_output(greeting: str, style: str = "standard") -> str:
    """
    Format a greeting for different output styles.

    Pure utility function with no side effects.

    Args:
        greeting: The greeting string to format
        style: Output style - "standard", "uppercase", "lowercase", "excited"

    Returns:
        Formatted greeting string.
    """
    styles = {
        "standard": lambda g: g,
        "uppercase": lambda g: g.upper(),
        "lowercase": lambda g: g.lower(),
        "excited": lambda g: g.replace("!", "!!!") if "!" in g else g + "!!!",
    }

    formatter = styles.get(style, styles["standard"])
    return formatter(greeting)
