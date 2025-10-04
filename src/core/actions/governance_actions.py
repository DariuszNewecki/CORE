# src/core/actions/governance_actions.py
"""
Action handlers for governance-related operations.
"""

from __future__ import annotations

import uuid

import yaml
from shared.logger import getLogger
from shared.models import PlanExecutionError, TaskParams

from .base import ActionHandler
from .context import PlanExecutorContext

log = getLogger("governance_actions")


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d
# ID: 81d33ff2-37a3-4686-a4a7-32c899d20705
class CreateProposalHandler(ActionHandler):
    """Handles the 'create_proposal' action."""

    @property
    # ID: e5562cbd-b81b-49f4-ae61-7ce318aec6fa
    def name(self) -> str:
        return "create_proposal"

    # ID: 426dd8a7-e224-4372-b6c4-40bc735d6c62
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        target_path = params.file_path
        content = params.code
        justification = params.justification

        if not all([target_path, content, justification]):
            raise PlanExecutionError("Missing required parameters for create_proposal.")

        proposal_id = str(uuid.uuid4())[:8]
        proposal_filename = (
            f"cr-{proposal_id}-{target_path.split('/')[-1].replace('.py','')}.yaml"
        )
        proposal_path = (
            context.file_handler.repo_path / ".intent/proposals" / proposal_filename
        )

        proposal_content = {
            "target_path": target_path,
            "action": "replace_file",
            "justification": justification,
            "content": content,
        }

        yaml_content = yaml.dump(
            proposal_content, indent=2, default_flow_style=False, sort_keys=True
        )
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(yaml_content, encoding="utf-8")
        log.info(f"🏛️  Created constitutional proposal: {proposal_filename}")

        if context.git_service.is_git_repo():
            context.git_service.add(str(proposal_path))
            context.git_service.commit(
                f"feat(proposal): Create proposal for {target_path}"
            )
