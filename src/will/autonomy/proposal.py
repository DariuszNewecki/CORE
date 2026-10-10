# src/will/autonomy/proposal.py
"""
A3 Proposal System - Autonomous Action Planning

A proposal is a bounded, validated plan for autonomous action.
It references actions from the registry, declares its scope,
and provides constitutional guarantees.

Database-backed, registry-native, designed for A3 autonomy.

ARCHITECTURE:
- Proposals are stored in PostgreSQL
- Actions are referenced by action_id (from registry)
- Validation is pre-execution
- Execution is via ActionExecutor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from shared.lifecycles.proposal import ProposalStatus
from shared.logger import getLogger


# Re-export for backward compatibility — canonical location is shared.lifecycles.proposal
__all__ = ["Proposal", "ProposalScope", "ProposalStatus"]

logger = getLogger(__name__)


# Constitutional blast bound for proposal scope.files.
# MUST match `.intent/enforcement/contracts/ProposalScope.json` files.maxItems.
# Authority: 2026-05-24 hardening-sweep blast-bound principle. A single
# proposal's per-execution blast is constitutionally bounded; larger scopes
# require the contract to be amended via ADR. Mirrored here so the bound is
# enforced at write time (Proposal.validate) in addition to audit time
# (ADR-056 D6 SchemaConformanceChecks).
_SCOPE_FILES_MAX_ITEMS = 50


@dataclass
# ID: 8cfd7a73-aecd-4f7e-bb0c-d65d888b7b7e
class ProposalScope:
    """
    Declares what a proposal will affect.

    This enables impact analysis and conflict detection.
    """

    files: list[str] = field(default_factory=list)
    """Files that will be modified"""

    modules: list[str] = field(default_factory=list)
    """Python modules affected"""

    symbols: list[str] = field(default_factory=list)
    """Specific symbols (functions/classes) changed"""

    policies: list[str] = field(default_factory=list)
    """Constitutional policies referenced"""

    # ID: f669fae8-c478-47f9-bec3-4b50a8cc0399
    def conflicts_with(self, other: ProposalScope) -> bool:
        """Check if this scope conflicts with another proposal."""
        return bool(
            set(self.files) & set(other.files)
            or set(self.modules) & set(other.modules)
            or set(self.symbols) & set(other.symbols)
        )


# ADR-168 Amendment 2026-10-10 A2: what a proposal is anchored to, and who
# owns the problem. "governor_request" is a prompt the governor decided,
# recorded verbatim (governor ruling 2026-10-10, option A).
ANCHOR_KINDS: tuple[str, ...] = ("finding", "issue", "adr", "governor_request")
PROBLEM_OWNERS: tuple[str, ...] = ("governor", "core")

# Key under constitutional_constraints where provenance is stored — beside
# the lineage markers and finding_ids already kept there (ADR-154 D3).
_PROVENANCE_KEY = "provenance"


@dataclass
# ID: a9dbbd56-9d53-4b84-b8af-6e6a714c67ba
class ProposalProvenance:
    """Who and why: the anchor, the problem owner, the producer, what it retires.

    ADR-168 Amendment 2026-10-10 A2. The anchor is context, never authority;
    authority is the approval. ``producer`` names who writes the bytes: for
    a proposal whose bytes are produced at execution (CORE's own lanes) it
    names the role, and the commit records the actual model (A6).
    ``retires`` names what the change removes or supersedes; empty means
    "nothing".
    """

    anchor_kind: str
    anchor_refs: list[str]
    problem_owner: str
    producer: str
    retires: list[str] = field(default_factory=list)

    # ID: 78c5d88c-d024-4202-9fea-3cbaaf02bfce
    def problems(self) -> list[str]:
        """Return why this provenance is not well-formed ([] when it is)."""
        errors: list[str] = []
        if self.anchor_kind not in ANCHOR_KINDS:
            errors.append(
                f"Provenance anchor_kind {self.anchor_kind!r} is not one of {list(ANCHOR_KINDS)}"
            )
        if not any(ref.strip() for ref in self.anchor_refs):
            errors.append("Provenance must name at least one anchor reference")
        if self.problem_owner not in PROBLEM_OWNERS:
            errors.append(
                f"Provenance problem_owner {self.problem_owner!r} is not one of {list(PROBLEM_OWNERS)}"
            )
        if not self.producer.strip():
            errors.append("Provenance must name the producer")
        # A finding is a problem CORE raised; a governor request is the
        # governor's. Issues and ADRs may be owned by either.
        if self.anchor_kind == "finding" and self.problem_owner != "core":
            errors.append("A finding-anchored proposal's problem owner is core")
        if self.anchor_kind == "governor_request" and self.problem_owner != "governor":
            errors.append(
                "A governor-request-anchored proposal's problem owner is the governor"
            )
        return errors

    # ID: df27bd89-ee21-4faa-8a3d-64e0c4335fce
    def to_dict(self) -> dict[str, Any]:
        """Serialise for storage under constitutional_constraints."""
        return {
            "anchor_kind": self.anchor_kind,
            "anchor_refs": list(self.anchor_refs),
            "problem_owner": self.problem_owner,
            "producer": self.producer,
            "retires": list(self.retires),
        }

    @classmethod
    # ID: 7f2a6820-d3b9-43ae-b176-81a2bef28ad3
    def from_dict(cls, data: dict[str, Any]) -> ProposalProvenance:
        """Deserialise from storage."""
        return cls(
            anchor_kind=str(data.get("anchor_kind", "")),
            anchor_refs=[str(r) for r in data.get("anchor_refs") or []],
            problem_owner=str(data.get("problem_owner", "")),
            producer=str(data.get("producer", "")),
            retires=[str(r) for r in data.get("retires") or []],
        )


@dataclass
# ID: 4da11b16-da1c-4bbb-88f6-5db76b9e2a0a
class RiskAssessment:
    """
    Risk analysis for a proposal.

    Derived from action impact levels and scope analysis.
    """

    overall_risk: str
    """safe, moderate, or high (proposal_risk enum per ADR-059 D1)"""

    action_risks: dict[str, str] = field(default_factory=dict)
    """Map of action_id -> impact_level"""

    risk_factors: list[str] = field(default_factory=list)
    """Identified risk factors"""

    mitigation: list[str] = field(default_factory=list)
    """Required mitigations"""

    # ID: 9037d8bc-c407-4787-99f6-18e09143f013
    def requires_approval(self) -> bool:
        """Whether this proposal needs human approval."""
        return self.overall_risk in ["moderate", "high"]


@dataclass
# ID: 8c3da43b-b6b2-4392-8720-56f77964076d
class ProposalAction:
    """
    A single step within a Proposal.

    References either an AtomicAction (via action_id) or a Flow (via flow_id).
    Exactly one of action_id or flow_id must be set. The other must be None.

    Backward compatibility: existing code using ProposalAction(action_id=...)
    is unchanged. flow_id is a new optional field defaulting to None.
    """

    action_id: str | None = None
    """AtomicAction from ActionRegistry (e.g., 'fix.format'). Mutually exclusive with flow_id."""

    flow_id: str | None = None
    """Flow from FlowRegistry (e.g., 'flow.fix_code'). Mutually exclusive with action_id."""

    parameters: dict[str, Any] = field(default_factory=dict)
    """Parameters passed to the action or flow at execution time."""

    order: int = 0
    """Execution order within the Proposal (for sequencing)."""

    def __post_init__(self) -> None:
        """Enforce that exactly one of action_id or flow_id is set."""
        if self.action_id is None and self.flow_id is None:
            raise ValueError(
                "ProposalAction requires exactly one of action_id or flow_id. Both are None."
            )
        if self.action_id is not None and self.flow_id is not None:
            raise ValueError(
                f"ProposalAction requires exactly one of action_id or flow_id. "
                f"Both are set: action_id={self.action_id!r}, flow_id={self.flow_id!r}"
            )

    @property
    # ID: 9accf55a-07f8-43f3-a271-4579205a6323
    def ref_id(self) -> str:
        """The action_id or flow_id, whichever is set."""
        return self.action_id or self.flow_id  # type: ignore[return-value]

    @property
    # ID: cd908d8f-dbf2-4e7c-9e13-b437345b75aa
    def ref_kind(self) -> str:
        """'action' if action_id is set, 'flow' if flow_id is set."""
        return "action" if self.action_id is not None else "flow"

    # ID: 78f087a3-9b56-4903-82d9-13cdb35b55e1
    def validate_exists(self) -> bool:
        """Verify the referenced action or flow exists in its registry."""
        if self.action_id is not None:
            from body.atomic.registry import action_registry

            return action_registry.get(self.action_id) is not None
        if self.flow_id is not None:
            from body.flows.registry import flow_registry

            return flow_registry.get(self.flow_id) is not None
        return False


def _resolve_impact(action_id: str, risk_mapping: dict[str, str]) -> str:
    """Resolve an action's governed impact_level from the action_risk mapping.

    ADR-008: impact_level is governed externally in
    .intent/enforcement/config/action_risk.yaml — never read from code or
    from registry-overlay state. The registry's ActionDefinition.impact_level
    field is only populated as a side-effect of ActionExecutor.__init__
    (executor.apply_risk_config), so any risk computation that runs before an
    executor exists in the process — as TestRemediatorWorker does — would read
    an empty string and silently misclassify. Resolving straight from the
    governed mapping decouples risk computation from executor-init ordering.

    Unknown / unmapped action_ids fail closed to "moderate" — an
    unclassified action is never treated as safe.
    """
    return risk_mapping.get(action_id, "moderate")


def _compute_flow_risk(
    flow_id: str,
    risk_mapping: dict[str, str],
    _visited: frozenset[str] = frozenset(),
) -> str:
    """Resolve a flow's risk as the max impact of its constituent steps.

    Impact for each ACTION step is resolved from the governed action_risk
    mapping (ADR-008) via _resolve_impact, not from registry-overlay state.
    Recurses through nested flow steps. Cycle-safe via _visited tracker.
    Falls back to "moderate" (conservative) when a flow cannot be resolved
    or a cycle is detected. ADR-046 D1.
    """
    from body.flows.registry import StepKind, flow_registry

    if flow_id in _visited:
        return "moderate"
    visited = _visited | {flow_id}

    flow_def = flow_registry.get(flow_id)
    if flow_def is None:
        return "moderate"

    # `impact` here can arrive in either of two vocabularies: ACTION steps
    # resolve via _resolve_impact (action_risk.yaml's impact_level vocabulary
    # — safe/moderate/dangerous), while FLOW steps recurse into this same
    # function and get back ITS OWN return value, which is already in the
    # proposal_risk output vocabulary (safe/moderate/high per ADR-059 D1).
    # "dangerous" and "high" name the same level in those two vocabularies,
    # not two different levels — the rank table must recognize both as
    # level 2, or a nested flow's "high" silently falls through the
    # fallback default below and gets demoted (G6 vocabulary-mismatch
    # defect; production-readiness assessment errata 2026-07-23 correction 1).
    risk_levels = {"safe": 0, "moderate": 1, "dangerous": 2, "high": 2}
    max_level = 0
    for step in flow_def.steps:
        if step.kind == StepKind.ACTION:
            impact = _resolve_impact(step.ref_id, risk_mapping)
        elif step.kind == StepKind.FLOW:
            impact = _compute_flow_risk(step.ref_id, risk_mapping, visited)
        elif step.kind == StepKind.COGNITIVE:
            # Cognitive steps are read/think only; write risk is carried by
            # the downstream ACTION step that consumes the produces output.
            impact = "safe"
        else:
            impact = "moderate"
        max_level = max(max_level, risk_levels.get(impact, 1))

    return ["safe", "moderate", "high"][max_level]


@dataclass
# ID: 7c009aef-daac-4c91-9b1f-0b40e700922b
class Proposal:
    """
    A3 Proposal - Bounded autonomous action plan.

    Core principles:
    - Database-backed (PostgreSQL is truth)
    - Registry-native (actions by ID)
    - Constitutionally governed
    - Execution-separated (proposal ≠ execution)

    Lifecycle (#885: created directly in PENDING — there is no pre-review
    holding state; see shared.lifecycles.proposal.ProposalStatus):
    1. PENDING: Created, awaiting approval in the review queue
    2. APPROVED: Cleared to execute
    3. EXECUTING: Currently running
    4. FINALIZING: Committed; consequence chain being recorded (ADR-148)
    5. COMPLETED/FAILED/REJECTED: Terminal states
    """

    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    """Unique proposal identifier"""

    goal: str = ""
    """What this proposal aims to achieve"""

    actions: list[ProposalAction] = field(default_factory=list)
    """Ordered list of actions to execute"""

    scope: ProposalScope = field(default_factory=ProposalScope)
    """What this proposal will affect"""

    risk: RiskAssessment | None = None
    """Risk analysis and mitigation"""

    status: ProposalStatus = ProposalStatus.PENDING
    """Current lifecycle status — created directly in the reviewable state (#885)"""

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "autonomous"  # or user identifier

    # Validation
    validation_checks: list[str] = field(default_factory=list)
    """Checks that must pass before execution"""

    validation_results: dict[str, bool] = field(default_factory=dict)
    """Results of validation checks"""

    # Execution tracking
    execution_started_at: datetime | None = None
    execution_completed_at: datetime | None = None
    execution_results: dict[str, Any] = field(default_factory=dict)
    """Results from each action execution"""

    # Constitutional
    constitutional_constraints: dict[str, Any] = field(default_factory=dict)
    """Policy boundaries that must be respected"""

    approval_required: bool = False
    """Whether human approval is needed"""

    approved_by: str | None = None
    """Who approved this proposal"""

    approved_at: datetime | None = None
    """When it was approved"""

    approval_authority: str | None = None
    """Authority under which approval was granted (URS Q2.A, NFR.5)."""

    # Failure tracking
    failure_reason: str | None = None
    """Why execution failed (if applicable)"""

    # ADR-168 Amendment 2026-10-10 A2
    provenance: ProposalProvenance | None = None
    """Anchor, problem owner, producer, what it retires. Required to submit;
    stored under constitutional_constraints (see ``constraints_for_storage``).
    Rows created before 2026-10-10 have none."""

    # ID: a0c3985a-5529-4c26-8cab-abe82e734abd
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate proposal is well-formed and executable.

        The submission checks (``check_submission``) plus the execution-side
        ones: a risk assessment exists, and a high-risk proposal is approved.

        Returns:
            (is_valid, list of error messages)
        """
        errors = self.check_submission()

        # 4. Must have risk assessment
        if self.risk is None:
            errors.append("Proposal must have risk assessment")

        # 5. High-risk proposals must have approval
        if self.risk and self.risk.overall_risk == "high":
            if not self.approved_by:
                errors.append("High-risk proposals require approval")

        return (len(errors) == 0, errors)

    # ID: 52d7daff-a340-43d7-ba30-53a5eaed822a
    def check_submission(self) -> list[str]:
        """Return why this proposal may not be submitted ([] when it may).

        A proposal awaiting approval is a valid submission, so this is
        ``validate()`` without its execution-side checks (risk assessed,
        high risk approved). Every submit path calls it before persisting:
        a proposal with no action, an action no registry knows, no declared
        file, or no provenance (ADR-168 Amendment 2026-10-10 A2) never
        enters the queue.
        """
        errors: list[str] = []

        # 1. Must have goal
        if not self.goal:
            errors.append("Proposal must have a goal")

        # 2. Must have actions
        if not self.actions:
            errors.append("Proposal must have at least one action")

        # 3. All actions/flows must exist in their respective registry
        for action in self.actions:
            if not action.validate_exists():
                errors.append(
                    f"{action.ref_kind.capitalize()} not found in registry: {action.ref_id}"
                )

        # 6. Must declare at least one file in scope (issue #191).
        # ADR-021 D5 punted execution-time enforcement; commit_paths raises
        # ValueError on empty scope.files at the very end of the success
        # branch and restore_paths silently no-ops on the failure branch.
        # Reject up-front here so the malformed proposal never reaches the
        # executor.
        if not self.scope.files:
            errors.append("Proposal must declare at least one file in scope.files")

        # 7. Must not exceed the constitutional blast bound on scope.files.
        # The bound is declared in .intent/enforcement/contracts/ProposalScope.json
        # (files.maxItems); mirrored here at _SCOPE_FILES_MAX_ITEMS for write-time
        # enforcement. A proposal above the bound never reaches the executor —
        # ProposalConsumerWorker would otherwise dispatch arbitrarily large blasts
        # in one cycle. Larger scopes require the contract to be amended via ADR.
        if len(self.scope.files) > _SCOPE_FILES_MAX_ITEMS:
            errors.append(
                f"Proposal scope.files declares {len(self.scope.files)} files, "
                f"exceeding the constitutional blast bound of "
                f"{_SCOPE_FILES_MAX_ITEMS} (ProposalScope.json files.maxItems). "
                f"Larger scopes require an ADR amending the contract."
            )

        # 8. Must say who and why (ADR-168 Amendment 2026-10-10 A2).
        if self.provenance is None:
            errors.append(
                "Proposal must carry provenance (anchor, problem owner, producer)"
            )
        else:
            errors.extend(self.provenance.problems())

        return errors

    # ID: bd436e51-c283-46cf-bbfe-4d9ae578296c
    def compute_risk(self) -> RiskAssessment:
        """
        Compute risk assessment based on actions.

        Returns:
            RiskAssessment with overall risk and factors
        """
        from body.atomic.registry import action_registry
        from shared.infrastructure.intent.action_risk import load_action_risk

        action_risks = {}
        risk_factors = []

        # Impact is governed externally (ADR-008): resolve it from the
        # action_risk mapping, NOT from ActionDefinition.impact_level, which is
        # only populated as a side-effect of ActionExecutor.__init__ and is
        # therefore empty in risk-compute contexts that run before any executor
        # exists (e.g. TestRemediatorWorker). Loaded once and threaded through
        # the flow recursion. See _resolve_impact.
        risk_mapping = load_action_risk()

        # Gather impact levels — Actions resolve directly; Flows resolve via
        # FlowRegistry as the max impact of constituent steps (ADR-046 D1).
        # Falls back to "moderate" for unresolvable flows / unmapped actions.
        for action in self.actions:
            if action.action_id is not None:
                if action_registry.get(action.action_id) is not None:
                    action_risks[action.action_id] = _resolve_impact(
                        action.action_id, risk_mapping
                    )
                else:
                    # An action no registry knows is never safe: skipping it
                    # let a proposal of only unknown actions score "safe".
                    action_risks[action.action_id] = "moderate"
            elif action.flow_id is not None:
                action_risks[action.flow_id] = _compute_flow_risk(
                    action.flow_id, risk_mapping
                )

        # Determine overall risk (highest action risk). action_risks values
        # can arrive in either vocabulary: direct actions resolve via
        # _resolve_impact (action_risk.yaml's safe/moderate/dangerous),
        # flow-typed actions carry _compute_flow_risk's own return value,
        # already in the proposal_risk output vocabulary (safe/moderate/
        # high per ADR-059 D1). "dangerous" and "high" name the same level
        # in those two vocabularies — both must rank as level 2, or a flow
        # wrapping a dangerous action silently falls through the fallback
        # default below and is misclassified "safe" (G6 vocabulary-mismatch
        # defect; production-readiness assessment errata 2026-07-23
        # correction 1).
        risk_levels = {"safe": 0, "moderate": 1, "dangerous": 2, "high": 2}
        max_risk = 0
        for impact in action_risks.values():
            level = risk_levels.get(impact, 0)
            max_risk = max(max_risk, level)

        overall_risk = ["safe", "moderate", "high"][max_risk]

        # Identify risk factors
        if overall_risk == "high":
            risk_factors.append("Contains high-risk actions")

        if len(self.scope.files) > 10:
            risk_factors.append(f"Large scope: {len(self.scope.files)} files")

        if any(impact == "moderate" for impact in action_risks.values()):
            risk_factors.append("Contains moderate-impact actions")

        # Determine mitigations
        mitigation = []
        if overall_risk == "high":
            mitigation.append("Human approval required")
            mitigation.append("Full system backup before execution")

        if overall_risk == "moderate":
            mitigation.append("Automated pre-flight checks")
            mitigation.append("Rollback plan prepared")

        self.risk = RiskAssessment(
            overall_risk=overall_risk,
            action_risks=action_risks,
            risk_factors=risk_factors,
            mitigation=mitigation,
        )

        self.approval_required = self.risk.requires_approval()

        return self.risk

    # ID: 03e9bc90-bc37-4592-8283-3fb7d3005022
    def constraints_for_storage(self) -> dict[str, Any]:
        """``constitutional_constraints`` with the provenance written in.

        Provenance lives beside the lineage markers and finding_ids already
        stored there (ADR-154 D3); the typed field is its in-memory form.
        """
        constraints = dict(self.constitutional_constraints)
        if self.provenance is not None:
            constraints[_PROVENANCE_KEY] = self.provenance.to_dict()
        return constraints

    # ID: e9fa7bda-3de4-43fa-ad27-50ddc4ad4aca
    def to_dict(self) -> dict[str, Any]:
        """
        Serialize proposal for database storage.

        Returns:
            Dictionary representation
        """
        return {
            "proposal_id": self.proposal_id,
            "goal": self.goal,
            "actions": [
                {
                    "action_id": a.action_id,
                    "flow_id": a.flow_id,
                    "parameters": a.parameters,
                    "order": a.order,
                }
                for a in self.actions
            ],
            "scope": {
                "files": self.scope.files,
                "modules": self.scope.modules,
                "symbols": self.scope.symbols,
                "policies": self.scope.policies,
            },
            "risk": (
                {
                    "overall_risk": self.risk.overall_risk,
                    "action_risks": self.risk.action_risks,
                    "risk_factors": self.risk.risk_factors,
                    "mitigation": self.risk.mitigation,
                }
                if self.risk
                else None
            ),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "validation_checks": self.validation_checks,
            "validation_results": self.validation_results,
            "execution_started_at": (
                self.execution_started_at.isoformat()
                if self.execution_started_at
                else None
            ),
            "execution_completed_at": (
                self.execution_completed_at.isoformat()
                if self.execution_completed_at
                else None
            ),
            "execution_results": self.execution_results,
            "constitutional_constraints": self.constraints_for_storage(),
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approval_authority": self.approval_authority,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    # ID: 9be0e0a5-3aca-45ab-8caf-26b6d7a6c67b
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        """
        Deserialize proposal from database.

        Args:
            data: Dictionary representation

        Returns:
            Proposal instance
        """
        # Parse actions
        actions = [
            ProposalAction(
                action_id=a.get("action_id"),
                flow_id=a.get("flow_id"),
                parameters=a.get("parameters", {}),
                order=a.get("order", 0),
            )
            for a in data.get("actions", [])
        ]

        # Parse scope
        scope_data = data.get("scope", {})
        scope = ProposalScope(
            files=scope_data.get("files", []),
            modules=scope_data.get("modules", []),
            symbols=scope_data.get("symbols", []),
            policies=scope_data.get("policies", []),
        )

        # Parse risk
        risk = None
        if data.get("risk"):
            risk_data = data["risk"]
            risk = RiskAssessment(
                overall_risk=risk_data["overall_risk"],
                action_risks=risk_data.get("action_risks", {}),
                risk_factors=risk_data.get("risk_factors", []),
                mitigation=risk_data.get("mitigation", []),
            )

        constraints = data.get("constitutional_constraints") or {}
        stored_provenance = constraints.get(_PROVENANCE_KEY)
        provenance = (
            ProposalProvenance.from_dict(stored_provenance)
            if isinstance(stored_provenance, dict)
            else None
        )

        return cls(
            proposal_id=data["proposal_id"],
            goal=data.get("goal", ""),
            actions=actions,
            scope=scope,
            risk=risk,
            status=ProposalStatus(data.get("status", ProposalStatus.PENDING.value)),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data.get("created_by", "autonomous"),
            validation_checks=data.get("validation_checks", []),
            validation_results=data.get("validation_results", {}),
            execution_started_at=(
                datetime.fromisoformat(data["execution_started_at"])
                if data.get("execution_started_at")
                else None
            ),
            execution_completed_at=(
                datetime.fromisoformat(data["execution_completed_at"])
                if data.get("execution_completed_at")
                else None
            ),
            execution_results=data.get("execution_results", {}),
            constitutional_constraints=constraints,
            approval_required=data.get("approval_required", False),
            approved_by=data.get("approved_by"),
            approved_at=(
                datetime.fromisoformat(data["approved_at"])
                if data.get("approved_at")
                else None
            ),
            approval_authority=data.get("approval_authority"),
            failure_reason=data.get("failure_reason"),
            provenance=provenance,
        )


@dataclass
# ID: 27f4e568-0534-485c-8103-7a877752672d
class ProposalConsequence:
    """
    Outcome record for an executed Proposal.

    Mirrors a row in core.proposal_consequences as written by
    ConsequenceLogService.record(). Captures pre/post execution SHAs,
    files touched, audit findings the execution resolved, and the
    constitutional rules that authorized the change. Used by
    ConsequenceLogService.find_cause_for_file() to attribute a file
    change back to the proposal that produced it.
    """

    proposal_id: str
    """Proposal that produced this consequence."""

    pre_execution_sha: str | None = None
    """Repository SHA before execution; None if not captured."""

    post_execution_sha: str | None = None
    """Repository SHA after execution; None if not captured."""

    files_changed: list[dict[str, Any]] = field(default_factory=list)
    """Files modified by the proposal. Each entry has at minimum a 'path' key."""

    findings_resolved: list[str] = field(default_factory=list)
    """Audit finding IDs that this execution cleared."""

    authorized_by_rules: list[str] = field(default_factory=list)
    """Constitutional rule IDs that authorized the execution."""

    recorded_at: datetime | None = None
    """When the consequence was recorded. None on construction; the DB sets it on insert."""
