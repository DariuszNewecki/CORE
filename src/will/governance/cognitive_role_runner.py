# src/will/governance/cognitive_role_runner.py
"""
Cognitive-role projection runner facade — Will-layer entry point for the
/cognitive-roles API (#821 Unit 2).

Unlike `sync_runner.py`'s async-dispatch+poll pattern (built for
full-repo audits that take real wall-clock time), `project.cognitive_roles`
touches at most a handful of core.cognitive_roles rows and completes in
milliseconds — so this facade is a synchronous, single-call wrapper with
no `core.sync_runs`-style tracking table.
"""

from __future__ import annotations

from shared.action_types import ActionResult
from shared.context import CoreContext


# ID: 5e9c3a7f-2d8b-4e1a-9c6f-3b8d2a5e7c1f
async def run_project_cognitive_roles(
    context: CoreContext, write: bool = False
) -> ActionResult:
    """Execute `project.cognitive_roles` via ActionExecutor.

    write=False diffs the YAML/DB capability projection read-only.
    write=True applies it, updating only the roles that drifted.
    """
    from body.atomic.executor import ActionExecutor

    executor = ActionExecutor(context)
    return await executor.execute("project.cognitive_roles", write=write)
