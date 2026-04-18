# src/cli/utils/helpers.py

"""
CLI helper utilities for common command patterns.
"""

from __future__ import annotations

import typer


# ID: 3c400acd-3d8c-4788-a63d-d96959985a94
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
