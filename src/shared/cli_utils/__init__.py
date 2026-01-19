# src/shared/cli_utils/__init__.py
"""
Constitutional CLI Framework.
Modularized Package Entry Point (V2.3).
"""

from __future__ import annotations

from .decorators import COMMAND_REGISTRY, async_command, core_command
from .display import (
    console,
    display_error,
    display_info,
    display_success,
    display_warning,
)
from .prompts import confirm_action


__all__ = [
    "COMMAND_REGISTRY",
    "async_command",
    "confirm_action",
    "console",
    "core_command",
    "display_error",
    "display_info",
    "display_success",
    "display_warning",
]
