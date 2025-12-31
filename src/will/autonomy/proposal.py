# src/will/autonomy/proposal.py
# ID: autonomy.proposal
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
from enum import Enum
from typing import Any
from uuid import uuid4

from body.atomic.registry import action_registry
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: proposal_status_enum
# ID: 86a456a9-13eb-415f-96e3-7a8622556dfe
class ProposalStatus(str, Enum):
    """Proposal lifecycle states."""

    DRAFT = "draft"  # Being created
    PENDING = "pending"  # Ready for review
    APPROVED = "approved"  # Authorized to execute
    EXECUTING = "executing"  # Currently running
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Execution failed
    REJECTED = "rejected"  # Rejected during review


# ID: proposal_scope
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


# ID: risk_assessment
@dataclass
# ID: 4da11b16-da1c-4bbb-88f6-5db76b9e2a0a
class RiskAssessment:
    """
    Risk analysis for a proposal.

    Derived from action impact levels and scope analysis.
    """

    overall_risk: str
    """safe, moderate, or dangerous"""

    action_risks: dict[str, str] = field(default_factory=dict)
    """Map of action_id -> impact_level"""

    risk_factors: list[str] = field(default_factory=list)
    """Identified risk factors"""

    mitigation: list[str] = field(default_factory=list)
    """Required mitigations"""

    # ID: 9037d8bc-c407-4787-99f6-18e09143f013
    def requires_approval(self) -> bool:
        """Whether this proposal needs human approval."""
        return self.overall_risk in ["moderate", "dangerous"]


# ID: proposal_action
@dataclass
# ID: 8c3da43b-b6b2-4392-8720-56f77964076d
class ProposalAction:
    """
    A single action within a proposal.

    References the registry and provides execution parameters.
    """

    action_id: str
    """Action from registry (e.g., 'fix.format')"""

    parameters: dict[str, Any] = field(default_factory=dict)
    """Action-specific parameters"""

    order: int = 0
    """Execution order (for sequencing)"""

    # ID: 9accf55a-07f8-43f3-a271-4579205a6323
    def validate_exists(self) -> bool:
        """Verify action exists in registry."""
        return action_registry.get(self.action_id) is not None


# ID: proposal
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

    Lifecycle:
    1. DRAFT: Created by analysis
    2. PENDING: Ready for validation
    3. APPROVED: Cleared to execute
    4. EXECUTING: Currently running
    5. COMPLETED/FAILED: Terminal states
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

    status: ProposalStatus = ProposalStatus.DRAFT
    """Current lifecycle status"""

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

    # Failure tracking
    failure_reason: str | None = None
    """Why execution failed (if applicable)"""

    # ID: proposal_validate
    # ID: a0c3985a-5529-4c26-8cab-abe82e734abd
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate proposal is well-formed and executable.

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        # 1. Must have goal
        if not self.goal:
            errors.append("Proposal must have a goal")

        # 2. Must have actions
        if not self.actions:
            errors.append("Proposal must have at least one action")

        # 3. All actions must exist in registry
        for action in self.actions:
            if not action.validate_exists():
                errors.append(f"Action not found in registry: {action.action_id}")

        # 4. Must have risk assessment
        if self.risk is None:
            errors.append("Proposal must have risk assessment")

        # 5. Dangerous proposals must have approval
        if self.risk and self.risk.overall_risk == "dangerous":
            if not self.approved_by:
                errors.append("Dangerous proposals require approval")

        return (len(errors) == 0, errors)

    # ID: proposal_compute_risk
    # ID: bd436e51-c283-46cf-bbfe-4d9ae578296c
    def compute_risk(self) -> RiskAssessment:
        """
        Compute risk assessment based on actions.

        Returns:
            RiskAssessment with overall risk and factors
        """
        action_risks = {}
        risk_factors = []

        # Gather action impact levels
        for action in self.actions:
            definition = action_registry.get(action.action_id)
            if definition:
                action_risks[action.action_id] = definition.impact_level

        # Determine overall risk (highest action risk)
        risk_levels = {"safe": 0, "moderate": 1, "dangerous": 2}
        max_risk = 0
        for impact in action_risks.values():
            level = risk_levels.get(impact, 0)
            max_risk = max(max_risk, level)

        overall_risk = ["safe", "moderate", "dangerous"][max_risk]

        # Identify risk factors
        if overall_risk == "dangerous":
            risk_factors.append("Contains dangerous actions")

        if len(self.scope.files) > 10:
            risk_factors.append(f"Large scope: {len(self.scope.files)} files")

        if any(impact == "moderate" for impact in action_risks.values()):
            risk_factors.append("Contains moderate-impact actions")

        # Determine mitigations
        mitigation = []
        if overall_risk == "dangerous":
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

    # ID: proposal_to_dict
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
            "constitutional_constraints": self.constitutional_constraints,
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "failure_reason": self.failure_reason,
        }

    # ID: proposal_from_dict
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
                action_id=a["action_id"],
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

        return cls(
            proposal_id=data["proposal_id"],
            goal=data.get("goal", ""),
            actions=actions,
            scope=scope,
            risk=risk,
            status=ProposalStatus(data.get("status", "draft")),
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
            constitutional_constraints=data.get("constitutional_constraints", {}),
            approval_required=data.get("approval_required", False),
            approved_by=data.get("approved_by"),
            approved_at=(
                datetime.fromisoformat(data["approved_at"])
                if data.get("approved_at")
                else None
            ),
            failure_reason=data.get("failure_reason"),
        )
