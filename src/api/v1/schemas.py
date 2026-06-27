# src/api/v1/schemas.py

"""
Shared Pydantic response models for API v1 routes.

CONSTITUTIONAL:
- Pure data layer — no I/O, no business logic, no layer imports.
- All models carry `from __future__ import annotations` per Python 3.12 project standard.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ID: a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d
class AsyncDispatchResponse(BaseModel):
    """Standard 202 response for all async-dispatch POST endpoints.

    Callers poll `href` to read the persisted run record once the
    background task completes.
    """

    run_id: str
    status: str
    href: str


# ID: b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e
class AuditRunResponse(BaseModel):
    """GET /v1/audit/runs/{run_id} response shape (ADR-054 amendment)."""

    run_id: str
    verdict: str | None
    finding_count: int
    blocking_count: int
    started_at: str | None
    finished_at: str | None
    status: str
    findings: list[Any]


# ID: c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f
class FixRunResponse(BaseModel):
    """GET /v1/fix/runs/{run_id} response shape (ADR-055 D2)."""

    run_id: str
    kind: str | None
    fix_id: str | None
    target_files: list[str] | None
    write: bool
    status: str
    requested_by: str | None
    requested_at: str | None
    started_at: str | None
    finished_at: str | None
    result: dict[str, Any] | None
    error: str | None


# ID: d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a
class RemediationRunResponse(BaseModel):
    """GET /v1/audit/remediations/{run_id} response shape."""

    run_id: str
    audit_run_id: str | None
    mode: str
    write: bool
    status: str
    requested_by: str | None
    requested_at: str | None
    started_at: str | None
    finished_at: str | None
    result: dict[str, Any] | None
    error: str | None


# ID: e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b
class ProposalActionItem(BaseModel):
    """Single action entry in a ProposalResponse."""

    action_id: str | None = None
    flow_id: str | None = None
    parameters: dict[str, Any] = {}
    order: int = 0


# ID: f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c
class ProposalResponse(BaseModel):
    """GET /v1/proposals/{id} response shape (Proposal.to_dict() surface)."""

    proposal_id: str
    goal: str
    actions: list[ProposalActionItem]
    scope: dict[str, Any]
    risk: dict[str, Any] | None = None
    status: str
    created_at: str
    created_by: str | None = None
    validation_checks: Any = None
    validation_results: Any = None
    execution_started_at: str | None = None
    execution_completed_at: str | None = None
    execution_results: Any = None
    constitutional_constraints: Any = None
    approval_required: bool = False
    approved_by: str | None = None
    approved_at: str | None = None
    approval_authority: str | None = None
    failure_reason: str | None = None
