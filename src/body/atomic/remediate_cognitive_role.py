# src/body/atomic/remediate_cognitive_role.py
# ID: actions.remediate_cognitive_role
"""
Atomic action for remediating ai.cognitive_role.no_hardcoded_string violations.

This action bridges audit findings to the CallSiteRewriter worker by:
1. Taking audit.violation findings for cognitive role rules
2. Converting them to prompt.artifact findings
3. Triggering the rewriter to fix the hardcoded strings
"""

from __future__ import annotations

import json
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
    requires_db=True,  # Needs DB to post to blackboard
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
    Remediate hardcoded cognitive role strings by posting prompt.artifact findings.

    This action is called by the proposal system when violations are found.
    It creates findings that the CallSiteRewriter will pick up and fix.

    Args:
        file_path: Path to the file containing the violation
        line_number: Line number where violation occurs (optional)
        rule: The specific rule being violated
        prompt_text: The hardcoded role string that was found
        **kwargs: Additional parameters

    Returns:
        ActionResult with success/failure status
    """
    if not file_path:
        return ActionResult.failure(
            message="Missing required parameter: file_path", data={"rule": rule}
        )

    try:
        from sqlalchemy import text

        from body.services.service_registry import service_registry

        # Post a prompt.artifact finding for CallSiteRewriter to claim
        async with service_registry.session() as session:
            # Create the payload that CallSiteRewriter expects
            payload = {
                "file_path": file_path,
                "line_number": line_number,
                "artifact_name": "cognitive_role_string",
                "rule": rule,
                "prompt_text": prompt_text,
                "input_vars": [],  # No input vars for this type
                "severity": "error",
            }

            # Insert into blackboard as prompt.artifact
            result = await session.execute(
                text(
                    """
                    INSERT INTO core.blackboard_entries
                    (entry_type, subject, payload, status, created_at)
                    VALUES (
                        'finding',
                        :subject,
                        :payload,
                        'open',
                        now()
                    )
                    RETURNING id
                """
                ),
                {
                    "subject": f"prompt.artifact::{file_path}",
                    "payload": json.dumps(payload),
                },
            )
            await session.commit()

            entry_id = result.scalar_one()

        logger.info(
            "Created prompt.artifact finding %s for %s (rule: %s)",
            entry_id,
            file_path,
            rule,
        )

        return ActionResult.success(
            message=f"Created remediation finding for {file_path}",
            data={"entry_id": str(entry_id), "file_path": file_path, "rule": rule},
        )

    except Exception as e:
        logger.error(
            "Failed to remediate cognitive role violation: %s", e, exc_info=True
        )
        return ActionResult.failure(
            message=f"Failed to create remediation finding: {e}",
            data={"file_path": file_path, "rule": rule},
        )
