# src/features/project_lifecycle/integration_service.py

"""Provides functionality for the integration_service module."""

from __future__ import annotations

import asyncio

from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c5928a71-8e5e-488e-9b89-0fb67b772bc3
class IntegrationError(RuntimeError):
    """Raised when the integration workflow fails."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


# ID: 22c20758-700f-46d1-9c39-43f2280ba73a
async def integrate_changes(context: CoreContext, commit_message: str) -> None:
    """
    Orchestrates the full, non-destructive, and intelligent integration of code changes
    by executing the constitutionally-defined `integration_workflow`.

    This workflow is designed to be safe and developer-friendly. If it fails,
    it halts and leaves the working directory in its current state for the
    developer to fix. It will never destroy uncommitted work.
    """
    git_service = context.git_service
    workflow_failed = False
    try:
        logger.info("Step 1: Staging all current changes...")
        git_service.add_all()
        staged_files = git_service.get_staged_files()
        if not staged_files:
            logger.info("No changes found to integrate. Working directory is clean.")
            return
        logger.info("   -> Staged %s file(s) for integration.", len(staged_files))
        workflow_policy = settings.load("charter.policies.operations.workflows_policy")
        integration_steps = workflow_policy.get("integration_workflow", [])
        for i, step in enumerate(integration_steps, 1):
            logger.info(
                "\nStep %s/%s: %s",
                i + 1,
                len(integration_steps) + 2,
                step["description"],
            )
            command_parts = step["command"].split()
            process = await asyncio.create_subprocess_exec(
                *command_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=settings.REPO_PATH,
            )
            stdout, stderr = await process.communicate()
            if stdout:
                logger.info(stdout.decode())
            if stderr:
                logger.warning(stderr.decode())
            if process.returncode != 0:
                logger.error("Step '%s' failed.", step["id"])
                if not step.get("continues_on_failure", False):
                    logger.error(
                        "Integration halted. Please fix the error above, then re-run the command."
                    )
                    workflow_failed = True
                    break
                else:
                    logger.info(
                        "   -> Continuing because step is marked as non-blocking."
                    )
        if workflow_failed:
            raise Exception("Workflow halted due to a failed step.")
        logger.info(
            "\nStep %s/%s: Committing all changes...",
            len(integration_steps) + 2,
            len(integration_steps) + 2,
        )
        git_service.commit(commit_message)
        logger.info("Successfully integrated and committed changes.")
    except Exception as e:
        logger.error("Integration process failed: %s", e)
        raise IntegrationError("Integration process failed.", exit_code=1) from e
