# src/features/self_healing/refactoring_proposal_writer.py

"""
Refactoring Proposal Writer - Constitutional Amendment Creation

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Write refactoring proposals
- Uses ActionExecutor for governed file creation
- Follows constitutional proposal format

Extracted from complexity_service.py to separate proposal creation.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


# ID: proposal_writer
# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class RefactoringProposalWriter:
    """
    Creates formal refactoring proposals via governed Action Gateway.

    Proposals are stored in work/proposals/ directory as YAML files.
    """

    def __init__(self, executor: ActionExecutor):
        """
        Initialize proposal writer.

        Args:
            executor: ActionExecutor for governed file operations
        """
        self.executor = executor

    # ID: writer_create_proposal
    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    async def create_proposal(self, proposal_plan: dict[str, Any], write: bool) -> bool:
        """
        Create a formal constitutional amendment proposal.

        Args:
            proposal_plan: Must contain 'target_path', 'justification', 'content'
            write: Whether to actually write the file

        Returns:
            True if proposal was created successfully
        """
        target_file_name = Path(proposal_plan["target_path"]).stem
        proposal_id = str(uuid.uuid4())[:8]
        proposal_filename = f"cr-refactor-{target_file_name}-{proposal_id}.yaml"

        # Resolve relative path for proposals directory
        proposals_dir_rel = str(settings.paths.proposals_dir.relative_to(REPO_ROOT))
        proposal_rel_path = f"{proposals_dir_rel}/{proposal_filename}"

        # Build proposal content
        proposal_content = {
            "target_path": proposal_plan["target_path"],
            "action": "replace_file",
            "justification": proposal_plan["justification"],
            "content": proposal_plan["content"],
        }

        yaml_str = yaml.dump(proposal_content, indent=2, sort_keys=False)

        # CONSTITUTIONAL GATEWAY: Create the proposal file
        result = await self.executor.execute(
            action_id="file.create",
            write=write,
            file_path=proposal_rel_path,
            code=yaml_str,
        )

        if result.ok:
            logger.info("Constitutional amendment proposed at: %s", proposal_rel_path)
            return True

        logger.error("Failed to create proposal: %s", result.data.get("error"))
        return False
