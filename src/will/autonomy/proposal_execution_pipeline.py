# src/will/autonomy/proposal_execution_pipeline.py
"""
ProposalExecutor pipeline-stage helpers.

Collaborator module for ProposalExecutor. Houses module-level async/sync
functions that implement each stage of the proposal execution pipeline
(pre-flight, claim, action loop, commit, consequence recording, rollback,
result envelope). Keeps ProposalExecutor a thin orchestrator and lets
execute_batch() share the same primitives as execute() instead of
inlining a parallel copy.

LAYER: will/autonomy — internal collaborator of ProposalExecutor. No
direct database access (uses service_registry like the orchestrator);
no file writes outside what the orchestrated atomic actions perform.
"""

from __future__ import annotations

from typing import Any


def _files_produced_by(action_results: dict[str, Any]) -> set[str]:
    """Collect every path actions reported via ``data['files_produced']``.

    Some actions — notably ``fix.modularity`` — write new files outside
    the proposal's declared ``scope.files``. Each such action lists those
    paths in its ``ActionResult.data['files_produced']``. The commit step
    unions this set with the declared scope so new files land in git
    alongside the scope-declared edits. Issue #297.

    Non-string and empty entries are filtered out defensively so a
    malformed action result can't corrupt the git-add invocation.
    """
    produced: set[str] = set()
    for result in action_results.values():
        data = result.get("data") or {}
        for path in data.get("files_produced") or []:
            if isinstance(path, str) and path:
                produced.add(path)
    return produced
