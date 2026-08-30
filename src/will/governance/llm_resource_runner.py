# src/will/governance/llm_resource_runner.py
"""
llm_resource authoring runner facade — Will-layer entry point for the
/llm-resources API (#821 Unit 3).

Synchronous, single-call wrapper over `author.llm_resource`, matching
cognitive_role_runner.py's shape: this validates/persists at most one row
and completes in milliseconds, so no core.sync_runs-style tracking table
is needed.
"""

from __future__ import annotations

from typing import Any

from shared.action_types import ActionResult
from shared.context import CoreContext


# ID: 2e6b0d4a-8c1f-4b5d-9e3a-7c1f5b9d3e7a
async def run_author_llm_resource(
    context: CoreContext, write: bool, definition: dict[str, Any]
) -> ActionResult:
    """Execute `author.llm_resource` via ActionExecutor.

    write=False validates the definition without persisting.
    write=True validates then creates-or-updates the row.
    """
    from body.atomic.executor import ActionExecutor

    executor = ActionExecutor(context)
    return await executor.execute(
        "author.llm_resource", write=write, definition=definition
    )
