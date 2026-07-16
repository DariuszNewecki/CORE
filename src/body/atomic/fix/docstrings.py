# src/body/atomic/fix/docstrings.py

"""fix.docstrings — generate and inject missing docstrings using AI.

Split from body/atomic/fix_actions.py (one action per module, #806).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action


if TYPE_CHECKING:
    from shared.context import CoreContext


@register_action(
    action_id="fix.docstrings",
    description="Generate and inject missing docstrings using AI",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["purity.docstrings.required"],
)
@atomic_action(
    action_id="fix.docstrings",
    intent="Autonomously generate missing docstrings via Coder LLM role",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: a3f91c7d-5e2b-4d8a-b6f0-c1e2d3f4a5b7
async def action_fix_docstrings(
    core_context: CoreContext,
    file_path: str | None = None,
    write: bool = False,
    limit: int = 0,
    **kwargs,
) -> ActionResult:
    """Generate and inject missing docstrings using the Coder LLM role.

    Two invocation modes:

    1. Targeted (autonomous loop): caller supplies ``file_path`` in kwargs,
       e.g. via ProposalExecutor expanding ``actions[i].parameters.file_path``.
       Only symbols inside that file are evaluated. Mirrors the pattern
       used by ``action_format_code`` and ``action_fix_modularity``.
    2. Sweep (legacy CLI): no ``file_path`` supplied. The action walks every
       symbol in the knowledge graph, as before. ``limit`` caps the symbol
       count in sweep mode; 0 means unlimited and is ignored when
       ``file_path`` is set (matches body's fix_docstrings contract).

    Before this change the action discarded ``**kwargs``, so every targeted
    proposal silently degraded to a full-tree sweep — one proposal hammered
    Ollama for the whole codebase regardless of its declared scope.
    """
    start = time.time()
    from body.self_healing.docstring_service import fix_docstrings

    try:
        await fix_docstrings(
            context=core_context, write=write, limit=limit, file_path=file_path
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.docstrings",
            ok=False,
            data={
                "error": str(e),
                "write": write,
                "file_path": file_path,
                "limit": limit,
            },
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.docstrings",
        ok=True,
        data={"write": write, "file_path": file_path, "limit": limit},
        duration_sec=time.time() - start,
    )
