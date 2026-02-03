# src/features/project_lifecycle/integration_service.py

"""
Integration Service - Orchestrates safe code integration workflow.

CONSTITUTIONAL COMPLIANCE:
- Loads workflow configuration from .intent/ structure
- Non-destructive operations (never destroys uncommitted work)
- Halts on failure to preserve developer work
- Uses constitutional workflow definitions
"""

from __future__ import annotations

import asyncio

from shared.config import settings
from shared.context import CoreContext
from shared.exceptions import CoreError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a97c6d24-1068-46db-a551-9b193be9ed8c
class IntegrationError(CoreError):
    """Raised when project integration fails."""


# ID: 22c20758-700f-46d1-9c39-43f2280ba73a
async def integrate_changes(context: CoreContext, commit_message: str) -> None:
    """
    Orchestrates the full, non-destructive, and intelligent integration of code changes
    by executing the constitutionally-defined integration workflow.

    This workflow is designed to be safe and developer-friendly. If it fails,
    it halts and leaves the working directory in its current state for the
    developer to fix. It will never destroy uncommitted work.

    Constitutional Alignment:
    - Loads workflow from .intent/workflows/ or .intent/phases/
    - Follows safe-by-default principles
    - Preserves uncommitted work on failure

    Args:
        context: CoreContext with Git service
        commit_message: Message for the commit

    Raises:
        IntegrationError: If integration workflow fails
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

        # FIXED: Updated to search new .intent/ structure
        # Try multiple possible locations for integration workflow
        workflow_policy = None
        possible_paths = [
            "workflows.integration",
            "workflows.full_feature_development",
            "phases.execution",
        ]

        for path in possible_paths:
            try:
                workflow_policy = settings.load(path)
                if workflow_policy and "integration_workflow" in workflow_policy:
                    logger.debug("Found integration workflow at: %s", path)
                    break
            except Exception:
                continue

        if not workflow_policy or "integration_workflow" not in workflow_policy:
            logger.warning(
                "Integration workflow not found in .intent/ structure, using default"
            )
            # Fallback to minimal default workflow
            integration_steps = [
                {
                    "id": "format",
                    "description": "Format code",
                    "command": "make format",
                    "continues_on_failure": False,
                },
                {
                    "id": "lint",
                    "description": "Lint code",
                    "command": "make lint",
                    "continues_on_failure": True,
                },
            ]
        else:
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
