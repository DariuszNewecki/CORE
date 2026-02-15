# src/body/workflows/__init__.py
# ID: a2cc3cee-595c-4632-b2e3-aeee71920b9d
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

from body.workflows.dev_sync_workflow import DevSyncWorkflow
from shared.models.workflow_models import WorkflowResult


__all__ = [
    "DevSyncWorkflow",
    "WorkflowResult",
]
