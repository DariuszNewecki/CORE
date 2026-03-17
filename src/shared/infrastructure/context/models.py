# src/shared/infrastructure/context/models.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TriggerType = Literal["cli", "workflow", "agent"]
PhaseType = Literal["parse", "load", "audit", "runtime", "execution"]


@dataclass
# ID: b79c2b21-c223-40bf-9293-47eb0b8626df
class ContextBuildRequest:
    """
    Canonical request for building a context packet.

    This is the single entrypoint for all context assembly inside CORE.
    The request declares the operational goal, invocation trigger,
    evaluation phase, and optional targeting hints.
    """

    goal: str
    trigger: TriggerType
    phase: PhaseType

    workflow_id: str | None = None
    stage_id: str | None = None

    target_files: list[str] = field(default_factory=list)
    target_symbols: list[str] = field(default_factory=list)
    target_paths: list[str] = field(default_factory=list)

    include_constitution: bool = True
    include_policy: bool = True
    include_symbols: bool = True
    include_vectors: bool = True
    include_runtime: bool = True


@dataclass
# ID: 63c589dd-c5ee-489b-afcd-0bb72efc62d6
class ContextPacket:
    """
    Constitution-aligned context packet.

    A ContextPacket is the minimal evidence set required to evaluate
    applicable rules at a declared CORE phase.
    """

    request: ContextBuildRequest

    header: dict[str, Any] = field(default_factory=dict)
    constitution: dict[str, Any] = field(default_factory=dict)
    policy: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


# Backward-compatible alias during migration.
ContextPackage = ContextPacket
