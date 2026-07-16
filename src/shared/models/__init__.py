# src/shared/models/__init__.py
"""
Makes all Pydantic models in this directory available for easy import.
"""

from __future__ import annotations

from .audit_models import AuditFinding, AuditSeverity, EvidenceClass
from .capability_models import CapabilityMeta
from .drift_models import DriftReport
from .embedding_payload import EmbeddingPayload
from .execution_models import (
    ExecutionTask,
    PlanExecutionError,
    PlannerConfig,
    TaskParams,
)
from .generation_mode import GenerationMode
from .grc_verdict import (
    Applicability,
    ApplicabilityAssessment,
    EvidenceItem,
    RequirementStatus,
    RequirementVerdict,
)
from .validation_result import ValidationResult
from .workflow_models import (
    DetailedPlan,
    DetailedPlanStep,
    ExecutionResults,
    PhaseResult,
    PhaseWorkflowResult,
)


__all__ = [
    # GRC verdict contract (ADR-118)
    "Applicability",
    "ApplicabilityAssessment",
    "AuditFinding",
    "AuditSeverity",
    "CapabilityMeta",
    # Workflow models
    "DetailedPlan",
    "DetailedPlanStep",
    "DriftReport",
    "EmbeddingPayload",
    "EvidenceClass",
    "EvidenceItem",
    "ExecutionResults",
    "ExecutionTask",
    "GenerationMode",
    "PhaseResult",
    "PhaseWorkflowResult",
    "PlanExecutionError",
    "PlannerConfig",
    "RequirementStatus",
    "RequirementVerdict",
    "TaskParams",
    "ValidationResult",
]
