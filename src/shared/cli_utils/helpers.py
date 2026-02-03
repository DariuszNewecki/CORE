# src/shared/cli_utils/helpers.py

"""
CLI helper utilities for common command patterns.
"""

from __future__ import annotations

import typer


# ID: deprecated-command-helper
# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
def deprecated_command(old: str, new: str) -> None:
    """
    Display deprecation warning for CLI commands.

    Shows yellow warning message indicating the old command is deprecated
    and should be replaced with the new canonical command.

    Args:
        old: Old deprecated command path
        new: New canonical command path

    Examples:
        >>> deprecated_command("diagnostics find-clusters", "inspect clusters")
        DEPRECATED: 'diagnostics find-clusters' -> use 'inspect clusters'

        >>> deprecated_command("manage database sync-capabilities", "manage database sync capabilities")
        DEPRECATED: 'manage database sync-capabilities' -> use 'manage database sync capabilities'
    """
    typer.secho(
        f"DEPRECATED: '{old}' -> use '{new}'",
        fg=typer.colors.YELLOW,
    )
