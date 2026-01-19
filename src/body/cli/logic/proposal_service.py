# src/body/cli/logic/proposal_service.py

"""
Proposal lifecycle management logic.
Headless redirector for V2.3 Octopus Synthesis.
"""

from __future__ import annotations

from collections.abc import Callable

import typer

from shared.config import settings
from shared.logger import getLogger

from .proposals.service import ProposalService


logger = getLogger(__name__)


# ID: afb5a8de-836f-4788-8fe0-f3cd86b463c6
def proposals_list_cmd() -> None:
    """CLI command: list all pending proposals."""
    logger.info("Finding pending constitutional proposals...")
    proposals = ProposalService(settings.REPO_PATH).list()
    if not proposals:
        logger.info("No pending proposals found.")
        return
    logger.info("Found %s pending proposal(s):", len(proposals))
    for prop in proposals:
        logger.info("  - **%s**: %s", prop.name, prop.justification.strip())
        logger.info("    Target: %s", prop.target_path)
        logger.info(
            "    Status: %s (%s)",
            prop.status,
            "Critical" if prop.is_critical else "Standard",
        )


def _safe_proposal_action(action_desc: str, action_func: Callable[[], None]) -> None:
    logger.info(action_desc)
    try:
        action_func()
    except Exception as e:
        logger.error("%s", e)
        raise typer.Exit(code=1)


# ID: 344d451b-a0fb-41f7-bc6f-979881b289dc
def proposals_sign_cmd(proposal_name: str) -> None:
    def _action():
        identity = typer.prompt("Enter your identity (e.g., name@domain.com)")
        ProposalService(settings.REPO_PATH).sign(proposal_name, identity)

    _safe_proposal_action(f"Signing proposal: {proposal_name}", _action)


# ID: bfd5a9e0-ceea-4196-b447-f0df152d1b66
async def proposals_approve_cmd(proposal_name: str, context=None) -> None:
    repo_root = (
        context.git_service.repo_path
        if context and context.git_service
        else settings.REPO_PATH
    )
    logger.info("Attempting to approve proposal: %s", proposal_name)
    try:
        await ProposalService(repo_root).approve(proposal_name)
    except Exception as e:
        logger.error("%s", e)
        raise typer.Exit(code=1)


# Aliases for CLI registry compatibility
proposals_list = proposals_list_cmd
proposals_sign = proposals_sign_cmd
proposals_approve = proposals_approve_cmd
