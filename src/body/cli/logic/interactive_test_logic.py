# src/body/cli/logic/interactive_test_logic.py

"""
Interactive test generation logic entry point.

This module maintains backwards compatibility with the original interface
while delegating to the modularized interactive_test package.

Constitutional Compliance:
- Backwards compatible: Same function signature as before
- Thin wrapper: Delegates to package
"""

from __future__ import annotations

from body.cli.logic.interactive_test.workflow import run_interactive_workflow
from shared.context import CoreContext


__all__ = ["run_interactive_test_generation"]


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
async def run_interactive_test_generation(
    target_file: str,
    core_context: CoreContext,
) -> bool:
    """
    Run interactive test generation workflow.

    This is the main entry point called by the CLI command.
    Delegates to the interactive_test package.

    Args:
        target_file: Module to generate tests for
        core_context: Core context with services

    Returns:
        True if successful, False if user cancelled
    """
    return await run_interactive_workflow(target_file, core_context)
