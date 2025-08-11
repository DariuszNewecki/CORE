# src/core/cli/guard.py
"""
This module is deprecated and will be removed.
The `core-admin` CLI provided by the `system` domain is now the primary
entry point for all governance and operational commands.
"""

from shared.logger import getLogger

log = getLogger(__name__)

def ensure_cli_entrypoint():
    """Provides functionality for the core domain."""
    log.warning("The `core-admin guard` command is deprecated and will be removed.")
    log.warning("Please use the main `core-admin` command from the `system` domain.")
    log.warning("For example: `poetry run core-admin guard drift`")

if __name__ == "__main__":
    ensure_cli_entrypoint()
