# src/shared/infrastructure/database/models/__init__.py

"""
Database models package.
Organized by Mind-Body-Will architecture.
"""

from __future__ import annotations

from .autonomous_proposals import AutonomousProposal
from .decision_traces import DecisionTrace
from .governance import AuditRun, ConstitutionalViolation
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
from .workers import BlackboardEntry, WorkerRegistry


__all__ = [
    "Action",
    "AgentDecision",
    "AgentMemory",
    "AuditRun",
    # Base for migrations and metadata
    "Base",
    # Workers (Blackboard)
    "BlackboardEntry",
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
    # Workers (Constitutional Autonomous Entities)
    "WorkerRegistry",
]
