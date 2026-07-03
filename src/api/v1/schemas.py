# src/api/v1/schemas.py

"""
Shared Pydantic response models for API v1 routes.

CONSTITUTIONAL:
- Pure data layer — no I/O, no business logic, no layer imports.
- All models carry `from __future__ import annotations` per Python 3.12 project standard.
- Every public API route MUST declare response_model= using a type defined here
  (architecture.api.response_must_use_declared_schema — reporting, ramps to blocking).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ── Async dispatch ────────────────────────────────────────────────────────────


# ID: a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d
class AsyncDispatchResponse(BaseModel):
    """Standard 202 response for all async-dispatch POST endpoints.

    Callers poll `href` to read the persisted run record once the
    background task completes.
    """

    run_id: str
    status: str
    href: str


# ── Audit runs ────────────────────────────────────────────────────────────────


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


# ── Fix runs ──────────────────────────────────────────────────────────────────


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


# ID: 3f1a2b4c-5d6e-4f7a-8b9c-0d1e2f3a4b5c
class FixIRResponse(BaseModel):
    """POST /v1/fix/ir synchronous response — the written scaffold path."""

    path: str


# ID: 4a2b3c5d-6e7f-4a8b-9c0d-1e2f3a4b5c6d
class ActionCommandItem(BaseModel):
    """Metadata for one registered atomic action (GET /v1/fix/commands)."""

    action_id: str
    description: str | None = None
    category: str | None = None
    policies: list[str] = []
    impact_level: str | None = None
    requires_db: bool = False
    requires_vectors: bool = False
    remediates: list[str] = []


# ID: 5b3c4d6e-7f8a-4b9c-0d1e-2f3a4b5c6d7e
class FixCommandListResponse(BaseModel):
    """GET /v1/fix/commands response — whitelisted action metadata."""

    count: int
    commands: list[ActionCommandItem]


# ── Remediation runs ──────────────────────────────────────────────────────────


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


# ── Proposals ─────────────────────────────────────────────────────────────────


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


# ── Lane (Assisted Remediation) ───────────────────────────────────────────────


# ID: 6c7d8e9f-0a1b-4c2d-3e4f-5a6b7c8d9e0f
class LaneBundleRule(BaseModel):
    """Rule metadata within a lane finding bundle (ADR-109 #653)."""

    id: str | None = None
    rationale: str | None = None
    in_registry: bool = False


# ID: 7d8e9f0a-1b2c-4d3e-4f5a-6b7c8d9e0f1a
class LaneBundle(BaseModel):
    """Context bundle attached to a delegated finding (ADR-109 #653)."""

    rule: LaneBundleRule
    remediation: dict[str, Any] | None = None


# ID: 8e9f0a1b-2c3d-4e4f-5a6b-7c8d9e0f1a2b
class LaneFindingItem(BaseModel):
    """A single delegated finding from the Assisted Remediation Lane."""

    id: str
    subject: str
    payload: dict[str, Any]
    created_at: str | None = None


# ID: 9f0a1b2c-3d4e-4f5a-6b7c-8d9e0f1a2b3c
class LaneFindingWithBundle(LaneFindingItem):
    """Delegated finding enriched with the ADR-109 #653 context bundle."""

    bundle: LaneBundle


# ID: 0a1b2c3d-4e5f-4a6b-7c8d-9e0f1a2b3c4d
class LaneFindingListResponse(BaseModel):
    """GET /v1/lane response — paginated delegated finding list."""

    count: int
    findings: list[LaneFindingItem]


# ID: 1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e
class LaneClaimResponse(BaseModel):
    """POST /v1/lane/{finding_id}/claim response."""

    finding_id: str
    claimed_by: str
    status: str


# ID: 2c3d4e5f-6a7b-4c8d-9e0f-1a2b3c4d5e6f
class LaneProposeResponse(BaseModel):
    """POST /v1/lane/{finding_id}/propose response (201)."""

    proposal_id: str
    status: str
    approval_required: bool
    scope_files: list[str]


# ── Census ────────────────────────────────────────────────────────────────────


# ID: 3d4e5f6a-7b8c-4d9e-0f1a-2b3c4d5e6f7a
class CensusRunResponse(BaseModel):
    """GET /v1/census/runs/{run_id} response.

    Intentionally omits `requested_by` (internal username) per #727.
    """

    run_id: str
    snapshot: bool
    baseline_name: str | None = None
    status: str
    requested_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


# ID: 4e5f6a7b-8c9d-4e0f-1a2b-3c4d5e6f7a8b
class CensusBaselineItem(BaseModel):
    """A single named census baseline record."""

    name: str
    snapshot_file: str
    git_commit: str | None = None
    created_at: str | None = None


# ID: 5f6a7b8c-9d0e-4f1a-2b3c-4d5e6f7a8b9c
class CensusBaselineCreateResponse(BaseModel):
    """POST /v1/census/baselines/{name} response."""

    baseline: CensusBaselineItem


# ID: 6a7b8c9d-0e1f-4a2b-3c4d-5e6f7a8b9c0d
class CensusBaselineListResponse(BaseModel):
    """GET /v1/census/baselines response."""

    count: int
    baselines: list[CensusBaselineItem]


# ID: 7b8c9d0e-1f2a-4b3c-4d5e-6f7a8b9c0d1e
class CensusDiffResponse(BaseModel):
    """GET /v1/census/diff response.

    `available=False` when no snapshot or baseline exists; `diff` carries
    the CensusDiff model_dump when available.
    """

    available: bool
    error: str | None = None
    baseline: str | None = None
    diff: dict[str, Any] | None = None
