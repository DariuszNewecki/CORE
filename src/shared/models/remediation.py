# src/shared/models/remediation.py
"""
Shared remediation data models.

AutoFixablePattern is the canonical transfer object for mapping audit
check IDs to autonomous fix actions. It is used by:
  - body.self_healing.remediation_models (MatchedPattern)
  - will.self_healing.remediation_pattern_matcher (pattern list)

The authoritative remediation map lives in:
  .intent/enforcement/mappings/remediation/auto_remediation.yaml

This dataclass is a runtime transfer object only — not a source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
# ID: dc64f3c1-b122-4032-ac7c-acf00f43f6d6
class AutoFixablePattern:
    """
    Maps an audit check_id pattern to an autonomous action handler.

    Used as a transfer object when passing remediation decisions
    between the pattern matcher and execution layers.
    """

    check_id_pattern: str  # Rule/check ID from audit finding (exact or prefix*)
    action_handler: str  # Action that can fix this violation
    confidence: float  # 0.0-1.0
    risk_level: str  # "low" | "medium" | "high"
    description: str  # Human-readable explanation
