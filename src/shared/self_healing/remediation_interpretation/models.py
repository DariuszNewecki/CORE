# src/shared/self_healing/remediation_interpretation/models.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
# ID: 2567710b-4d4c-496b-8241-58bc42a1ded6
class NormalizedFinding:
    """
    Stable remediation-oriented representation of a blackboard finding.

    This model sits downstream of AuditViolationSensor. The sensor already
    normalizes raw audit engine outputs into blackboard payloads; this model
    normalizes those claimed blackboard findings into a deterministic shape
    suitable for architectural interpretation and remediation planning.
    """

    finding_id: str
    subject: str
    rule_id: str
    rule_namespace: str
    file_path: str
    line_number: int | None
    message: str
    severity: str
    dry_run: bool
    raw_payload: dict[str, Any] = field(default_factory=dict)
    raw_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
# ID: 4a055170-f777-462b-819f-e0612a2e7fe5
class FileRole:
    """
    Deterministic interpretation of the file's architectural role.

    role_id:
        Fine-grained role within the layer, e.g.:
        - worker.sensor
        - worker.actor
        - service
        - route
        - repository
        - model
        - utility
        - unknown

    layer:
        High-level constitutional layer inferred from path and/or structure:
        - mind
        - will
        - body
        - shared
        - unknown
    """

    role_id: str
    layer: str
    confidence: float
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
# ID: 3cc9401a-6398-488e-a22e-310982487f56
class ResponsibilityCluster:
    """
    One inferred responsibility area within a file.

    This is intentionally lightweight for the first implementation phase.
    It lets the interpreter express that a file may be carrying multiple
    concerns, which is central to architectural reasoning for rules like
    max_file_size, modularity, coupling, or boundary violations.
    """

    name: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)


@dataclass(slots=True)
# ID: 3a9acd7d-9b37-42b8-9936-cee55f8754e4
class RemediationStrategy:
    """
    Candidate remediation strategy ranked before LLM proposal generation.

    score:
        Deterministic integer score produced by StrategySelector. Higher is
        better. Used by choose_recommended() to apply the minimum-threshold
        gate. Included in to_dict() / to_brief_dict() so callers can see
        the evidence trail that produced it.

    preserves_contract:
        Indicates whether the strategy is expected to preserve externally
        visible behavior/contracts while resolving the violation.

    risk_level:
        Lightweight deterministic risk signal:
        - low
        - medium
        - high
    """

    strategy_id: str
    summary: str
    rationale: str
    risk_level: str
    preserves_contract: bool
    evidence: list[str] = field(default_factory=list)
    score: int = 0


@dataclass(slots=True)
# ID: 5acaac4c-f819-4461-9d45-6d1fd434ab27
class ReasoningBrief:
    """
    Bounded deterministic interpretation artifact passed into the existing
    PromptModel-based proposal path.

    This is the bridge between:
      audit finding  -> architectural interpretation -> LLM proposal generation

    The brief must stay concise, explicit, and explainable. It is not a
    chain-of-thought substitute. It is a governed planning artifact.
    """

    file_path: str
    file_role: FileRole
    findings: list[NormalizedFinding] = field(default_factory=list)
    responsibility_clusters: list[ResponsibilityCluster] = field(default_factory=list)
    candidate_strategies: list[RemediationStrategy] = field(default_factory=list)
    recommended_strategy: RemediationStrategy | None = None
    constraints: list[str] = field(default_factory=list)
    architectural_notes: list[str] = field(default_factory=list)

    # ID: 40ce3258-a2e2-4ca2-bb23-a9c6718eb0d0
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the brief."""
        return {
            "file_path": self.file_path,
            "file_role": {
                "role_id": self.file_role.role_id,
                "layer": self.file_role.layer,
                "confidence": self.file_role.confidence,
                "evidence": list(self.file_role.evidence),
            },
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "rule_id": f.rule_id,
                    "rule_namespace": f.rule_namespace,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "message": f.message,
                    "severity": f.severity,
                }
                for f in self.findings
            ],
            "responsibility_clusters": [
                {
                    "name": c.name,
                    "summary": c.summary,
                    "evidence": list(c.evidence),
                    "symbols": list(c.symbols),
                }
                for c in self.responsibility_clusters
            ],
            "candidate_strategies": [
                {
                    "strategy_id": s.strategy_id,
                    "summary": s.summary,
                    "rationale": s.rationale,
                    "risk_level": s.risk_level,
                    "preserves_contract": s.preserves_contract,
                    "evidence": list(s.evidence),
                    "score": s.score,
                }
                for s in self.candidate_strategies
            ],
            "recommended_strategy": (
                {
                    "strategy_id": self.recommended_strategy.strategy_id,
                    "summary": self.recommended_strategy.summary,
                    "rationale": self.recommended_strategy.rationale,
                    "risk_level": self.recommended_strategy.risk_level,
                    "preserves_contract": self.recommended_strategy.preserves_contract,
                    "evidence": list(self.recommended_strategy.evidence),
                    "score": self.recommended_strategy.score,
                }
                if self.recommended_strategy is not None
                else None
            ),
            "constraints": list(self.constraints),
            "architectural_notes": list(self.architectural_notes),
        }
