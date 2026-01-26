# src/will/autonomy/proposal_mapper.py

"""
Proposal Mapper - Domain/Database Model Conversion

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Convert between Proposal and AutonomousProposal
- Stateless utility class
- No database access

Extracted from ProposalRepository to separate data transformation concerns.
"""

from __future__ import annotations

from typing import Any

from will.autonomy.proposal import Proposal


# ID: proposal_mapper
# ID: 8d7c9f1e-2a4b-5c6d-7e8f-9a0b1c2d3e4f
class ProposalMapper:
    """Converts between Proposal domain model and AutonomousProposal database model."""

    @staticmethod
    # ID: mapper_to_db
    # ID: f1e2d3c4-b5a6-7890-abcd-ef1234567890
    def to_db_model(proposal: Proposal, db_class: type) -> Any:
        """
        Convert domain Proposal to database AutonomousProposal.

        Args:
            proposal: Domain model
            db_class: AutonomousProposal class (passed to avoid import)

        Returns:
            Database model instance
        """
        return db_class(
            proposal_id=proposal.proposal_id,
            goal=proposal.goal,
            status=proposal.status.value,
            actions=[
                {"action_id": a.action_id, "parameters": a.parameters, "order": a.order}
                for a in proposal.actions
            ],
            scope={
                "files": proposal.scope.files,
                "modules": proposal.scope.modules,
                "symbols": proposal.scope.symbols,
                "policies": proposal.scope.policies,
            },
            risk=(
                {
                    "overall_risk": proposal.risk.overall_risk,
                    "action_risks": proposal.risk.action_risks,
                    "risk_factors": proposal.risk.risk_factors,
                    "mitigation": proposal.risk.mitigation,
                }
                if proposal.risk
                else None
            ),
            created_at=proposal.created_at,
            created_by=proposal.created_by,
            validation_checks=proposal.validation_checks,
            validation_results=proposal.validation_results,
            execution_started_at=proposal.execution_started_at,
            execution_completed_at=proposal.execution_completed_at,
            execution_results=proposal.execution_results,
            constitutional_constraints=proposal.constitutional_constraints,
            approval_required=proposal.approval_required,
            approved_by=proposal.approved_by,
            approved_at=proposal.approved_at,
            failure_reason=proposal.failure_reason,
        )

    @staticmethod
    # ID: mapper_from_db
    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    def from_db_model(db_proposal: Any) -> Proposal:
        """
        Convert database AutonomousProposal to domain Proposal.

        Args:
            db_proposal: Database model instance

        Returns:
            Domain model
        """
        data = {
            "proposal_id": db_proposal.proposal_id,
            "goal": db_proposal.goal,
            "actions": db_proposal.actions,
            "scope": db_proposal.scope,
            "risk": db_proposal.risk,
            "status": db_proposal.status,
            "created_at": db_proposal.created_at.isoformat(),
            "created_by": db_proposal.created_by,
            "validation_checks": db_proposal.validation_checks,
            "validation_results": db_proposal.validation_results,
            "execution_started_at": (
                db_proposal.execution_started_at.isoformat()
                if db_proposal.execution_started_at
                else None
            ),
            "execution_completed_at": (
                db_proposal.execution_completed_at.isoformat()
                if db_proposal.execution_completed_at
                else None
            ),
            "execution_results": db_proposal.execution_results,
            "constitutional_constraints": db_proposal.constitutional_constraints,
            "approval_required": db_proposal.approval_required,
            "approved_by": db_proposal.approved_by,
            "approved_at": (
                db_proposal.approved_at.isoformat() if db_proposal.approved_at else None
            ),
            "failure_reason": db_proposal.failure_reason,
        }
        return Proposal.from_dict(data)

    @staticmethod
    # ID: mapper_update_db
    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
    def update_db_model(db_proposal: Any, proposal: Proposal) -> None:
        """
        Update database model fields from domain model.

        Args:
            db_proposal: Database model to update (mutated in place)
            proposal: Source domain model
        """
        db_proposal.goal = proposal.goal
        db_proposal.status = proposal.status.value
        db_proposal.actions = [
            {"action_id": a.action_id, "parameters": a.parameters, "order": a.order}
            for a in proposal.actions
        ]
        db_proposal.scope = {
            "files": proposal.scope.files,
            "modules": proposal.scope.modules,
            "symbols": proposal.scope.symbols,
            "policies": proposal.scope.policies,
        }
        db_proposal.risk = (
            {
                "overall_risk": proposal.risk.overall_risk,
                "action_risks": proposal.risk.action_risks,
                "risk_factors": proposal.risk.risk_factors,
                "mitigation": proposal.risk.mitigation,
            }
            if proposal.risk
            else None
        )
        db_proposal.validation_checks = proposal.validation_checks
        db_proposal.validation_results = proposal.validation_results
        db_proposal.execution_started_at = proposal.execution_started_at
        db_proposal.execution_completed_at = proposal.execution_completed_at
        db_proposal.execution_results = proposal.execution_results
        db_proposal.constitutional_constraints = proposal.constitutional_constraints
        db_proposal.approval_required = proposal.approval_required
        db_proposal.approved_by = proposal.approved_by
        db_proposal.approved_at = proposal.approved_at
        db_proposal.failure_reason = proposal.failure_reason
