# src/will/workflows/__init__.py
"""
Workflow Orchestrators - Constitutional Composition

Workflows compose atomic actions into governed, multi-phase operations.
Each workflow has:
- Declared goal
- Organized phases
- Structured results
- Full audit trail
- Constitutional validation
"""

from __future__ import annotations

from shared.models.workflow_models import WorkflowResult
from will.workflows.dev_sync_workflow import DevSyncWorkflow


__all__ = [
    "DevSyncWorkflow",
    "WorkflowResult",
]
