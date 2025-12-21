# src/shared/infrastructure/database/models/__init__.py

"""
CORE v2.2 Schema - Modular SQLAlchemy models.
Organized by Mind-Body-Will architecture.
"""

from __future__ import annotations

from .governance import AuditRun, ConstitutionalViolation, Proposal, ProposalSignature
from .knowledge import Base, Capability, Domain, Symbol, SymbolCapabilityLink
from .learning import AgentDecision, AgentMemory, Feedback
from .operations import Action, CognitiveRole, LlmResource, Task
from .system import (
    CliCommand,
    ContextPacket,
    Migration,
    Northstar,
    RuntimeService,
    RuntimeSetting,
)
from .vectors import RetrievalFeedback, SemanticCache, SymbolVectorLink, VectorSyncLog


__all__ = [
    "Action",
    "AgentDecision",
    "AgentMemory",
    "AuditRun",
    # Base for migrations and metadata
    "Base",
    "Capability",
    # System Metadata & Artifacts
    "CliCommand",
    "CognitiveRole",
    "ConstitutionalViolation",
    "ContextPacket",
    "Domain",
    # Learning & Feedback (Will)
    "Feedback",
    "LlmResource",
    "Migration",
    "Northstar",
    # Governance Layer (Constitution)
    "Proposal",
    "ProposalSignature",
    "RetrievalFeedback",
    "RuntimeService",
    "RuntimeSetting",
    "SemanticCache",
    # Knowledge Layer (Mind)
    "Symbol",
    "SymbolCapabilityLink",
    # Vector Integration
    "SymbolVectorLink",
    # Operations Layer (Body)
    "Task",
    "VectorSyncLog",
]
