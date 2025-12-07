# src/features/project_lifecycle/integration_service.py

"""Provides functionality for the integration_service module."""

from __future__ import annotations

import subprocess

import typer
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

logger = getLogger(__name__)


# ID: 469268e9-e747-4e6d-8aa5-c058e4dcaf9a
async def integrate_changes(context: CoreContext, commit_message: str):
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
        logger.info(f"   -> Staged {len(staged_files)} file(s) for integration.")
        workflow_policy = settings.load("charter.policies.operations.workflows_policy")
        integration_steps = workflow_policy.get("integration_workflow", [])
        for i, step in enumerate(integration_steps, 1):
            logger.info(
                f"\nStep {i + 1}/{len(integration_steps) + 2}: {step['description']}"
            )
            command_parts = step["command"].split()
            process = subprocess.run(
                command_parts, capture_output=True, text=True, cwd=settings.REPO_PATH
            )
            if process.stdout:
                logger.info(process.stdout)
            if process.stderr:
                logger.warning(process.stderr)
            if process.returncode != 0:
                logger.error(f"Step '{step['id']}' failed.")
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
            f"\nStep {len(integration_steps) + 2}/{len(integration_steps) + 2}: Committing all changes..."
        )
        git_service.commit(commit_message)
        logger.info("Successfully integrated and committed changes.")
    except Exception as e:
        logger.error("Integration process failed: %s", e)
        raise typer.Exit(code=1)
