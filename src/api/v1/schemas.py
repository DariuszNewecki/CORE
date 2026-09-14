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


# ── Cognitive-role projection (#821 Unit 2) ────────────────────────────────────


# ID: b3e7c1a9-4f8d-4b2e-9a6c-1d7f3e8b2c5a
class CognitiveRoleProjectionResponse(BaseModel):
    """Response for POST /v1/cognitive-roles/project.

    `data` carries the ActionResult.data shape from `project.cognitive_roles`:
    in_sync, drift, db_only_roles, yaml_only_roles, non_canonical, dry_run,
    and (when write=True) applied/blocked.
    """

    ok: bool
    data: dict[str, Any]
    duration_sec: float


# ── llm_resources authoring (#821 Unit 3) ──────────────────────────────────────


# ID: 3f7c1e5a-9d2b-4c6e-a0f4-8b2d6a0c4e8f
class LlmResourceAuthoringResponse(BaseModel):
    """Response for POST /v1/llm-resources/author.

    `data` carries the ActionResult.data shape from `author.llm_resource`:
    valid, violations, dry_run, and (on a successful write) `resource`.
    """

    ok: bool
    data: dict[str, Any]
    duration_sec: float


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


# ID: cdd1d849-df18-4c26-89b1-d5380d0fecb5
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


# ID: 4d400b0b-e01b-4169-bd0f-b3e45ab4fb97
class FixCommandListResponse(BaseModel):
    """GET /v1/fix/commands response — whitelisted action metadata."""

    count: int
    commands: list[ActionCommandItem]


# ── Remediation runs ──────────────────────────────────────────────────────────


# ID: a8926799-be01-4b50-b367-16349c35038c
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


# ── Governance chain ──────────────────────────────────────────────────────────


# ID: f9fa4af8-b42b-4055-8cf0-f27110f7d425
class FindingEvidence(BaseModel):
    """A single blackboard finding linked to a proposal."""

    entry_id: str
    subject: str | None = None
    status: str | None = None
    check_id: str | None = None
    rule_id: str | None = None
    file_path: str | None = None
    severity: str | None = None
    evidence: Any | None = None
    evidence_class: str | None = None
    created_at: str | None = None


# ID: d72c4f19-5869-4d07-878d-ef678fc19561
class ProposalSummary(BaseModel):
    """Proposal fields relevant to the governance chain."""

    proposal_id: str
    goal: str
    status: str
    risk: dict[str, Any] | None = None
    approval_authority: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    execution_results: dict[str, Any] | None = None
    created_by: str | None = None
    created_at: str
    failure_reason: str | None = None


# ID: 7164f225-7fda-4582-81fa-d2f65cb5650d
class ConsequenceRecord(BaseModel):
    """Execution consequence: what the proposal actually changed."""

    pre_execution_sha: str | None = None
    post_execution_sha: str | None = None
    files_changed: list[Any] = []
    findings_resolved: list[Any] = []
    authorized_by_rules: list[Any] = []
    recorded_at: str


# ID: 1782750c-371c-441f-8862-c42ff4ced4fe
class GovernanceChainResponse(BaseModel):
    """GET /v1/proposals/{id}/chain and /v1/findings/{id}/chain response.

    Traces a finding from detection through approval, execution, and file
    changes. consequence is None when the proposal has not yet been executed.
    """

    proposal: ProposalSummary
    findings: list[FindingEvidence] = []
    consequence: ConsequenceRecord | None = None


# ── Proposals ─────────────────────────────────────────────────────────────────


# ID: a3555752-a120-4726-b02f-aeb213033785
class ProposalActionItem(BaseModel):
    """Single action entry in a ProposalResponse."""

    action_id: str | None = None
    flow_id: str | None = None
    parameters: dict[str, Any] = {}
    order: int = 0


# ID: ed8dd1a6-2970-4a3c-8ed7-2c86f040cb6c
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


# ID: e122f23a-e4b2-44e1-8860-5359d6c887b4
class LaneBundleRule(BaseModel):
    """Rule metadata within a lane finding bundle (ADR-109 #653)."""

    id: str | None = None
    rationale: str | None = None
    in_registry: bool = False


# ID: 87a590ef-ad76-4c50-b442-efb99cbb7cc9
class LaneBundle(BaseModel):
    """Context bundle attached to a delegated finding (ADR-109 #653)."""

    rule: LaneBundleRule
    remediation: dict[str, Any] | None = None


# ID: df6cb07b-19dd-4013-9b5c-dae1ca48e1aa
class LaneFindingItem(BaseModel):
    """A single delegated finding from the Assisted Remediation Lane."""

    id: str
    subject: str
    payload: dict[str, Any]
    created_at: str | None = None


# ID: 4fed5e01-9d32-40d8-9a72-9838a7b1a580
class LaneFindingWithBundle(LaneFindingItem):
    """Delegated finding enriched with the ADR-109 #653 context bundle."""

    bundle: LaneBundle


# ID: fac60698-1614-4e2c-8f6b-0a805f7aa13c
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


# ID: c36d9db2-a3dd-427d-8cd8-4357abf615dd
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


# ID: b28bad4b-0a94-4fef-921d-e183e237987f
class CensusBaselineItem(BaseModel):
    """A single named census baseline record."""

    name: str
    snapshot_file: str
    git_commit: str | None = None
    created_at: str | None = None


# ID: f82efd2c-109d-4227-ba40-fb250641ede9
class CensusBaselineCreateResponse(BaseModel):
    """POST /v1/census/baselines/{name} response."""

    baseline: CensusBaselineItem


# ID: c2cad90b-6403-4276-a6e7-ed298ecc3f7f
class CensusBaselineListResponse(BaseModel):
    """GET /v1/census/baselines response."""

    count: int
    baselines: list[CensusBaselineItem]


# ID: 6183dbb5-9c23-43f0-80f9-43d074246b2a
class CensusDiffResponse(BaseModel):
    """GET /v1/census/diff response.

    `available=False` when no snapshot or baseline exists; `diff` carries
    the CensusDiff model_dump when available.
    """

    available: bool
    error: str | None = None
    baseline: str | None = None
    diff: dict[str, Any] | None = None
