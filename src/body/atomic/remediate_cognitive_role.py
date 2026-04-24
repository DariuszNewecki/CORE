# src/body/atomic/remediate_cognitive_role.py
# ID: actions.remediate_cognitive_role
"""
Atomic action for remediating ai.cognitive_role.no_hardcoded_string violations.

This action bridges audit findings to the CallSiteRewriter worker by:
1. Taking audit.violation findings for cognitive role rules
2. Preparing prompt.artifact finding data for the calling Worker to post
   via self.post_finding()
3. Triggering the rewriter to fix the hardcoded strings

The action does not write to the blackboard itself — ADR-011 requires
that all blackboard INSERTs flow through Worker attribution. The calling
Worker (ProposalConsumerWorker) posts the finding described in
ActionResult.data["finding_to_post"].
"""

from __future__ import annotations

from typing import Any

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionResult
from shared.logger import getLogger


logger = getLogger(__name__)


@register_action(
    action_id="remediate.cognitive_role",
    description="Fix hardcoded cognitive role strings (Architect, Coder, etc.) in source files",
    category=ActionCategory.FIX,
    policies=[
        "governance.dangerous_execution_primitives",
        "autonomy.tracing.mandatory",
    ],
    impact_level="moderate",  # Changes code but with canary protection
    requires_db=False,  # Action no longer touches the DB; caller posts the finding
    requires_vectors=False,
    remediates=[
        "ai.cognitive_role.no_hardcoded_string",
        # Add other related check_ids here if they exist
    ],
)
# ID: bf9420e3-f4ca-4cdf-aa11-7a9ecfa2a050
async def remediate_cognitive_role(
    file_path: str | None = None,
    line_number: int | None = None,
    rule: str = "ai.cognitive_role.no_hardcoded_string",
    prompt_text: str = "",
    **kwargs: Any,
) -> ActionResult:
    """
    Prepare prompt.artifact finding data for the calling Worker to post.

    This action is called by the proposal system when violations are found.
    It does NOT write to the blackboard itself — per ADR-011, every INSERT
    into core.blackboard_entries must flow through Worker attribution.
    The action constructs the finding shape (subject + payload) and returns
    it in ActionResult.data["finding_to_post"]; ProposalConsumerWorker
    posts via self.post_finding() as part of its post-execution handling.

    Args:
        file_path: Path to the file containing the violation
        line_number: Line number where violation occurs (optional)
        rule: The specific rule being violated
        prompt_text: The hardcoded role string that was found
        **kwargs: Additional parameters

    Returns:
        ActionResult with finding_to_post in data for the caller to post.
    """
    if not file_path:
        return ActionResult.failure(
            message="Missing required parameter: file_path", data={"rule": rule}
        )

    payload = {
        "file_path": file_path,
        "line_number": line_number,
        "artifact_name": "cognitive_role_string",
        "rule": rule,
        "prompt_text": prompt_text,
        "input_vars": [],  # No input vars for this type
        "severity": "error",
    }

    return ActionResult.success(
        message=f"Prepared prompt.artifact finding for {file_path}",
        data={
            "finding_to_post": {
                "subject": f"prompt.artifact::{file_path}",
                "payload": payload,
            },
            "file_path": file_path,
            "rule": rule,
        },
    )
