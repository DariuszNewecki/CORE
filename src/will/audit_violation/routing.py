# src/will/audit_violation/routing.py
"""
Finding routing table for AuditViolationSensor (ADR-095 D4).

Architectural-judgment rules carry a ``route_to`` marker on their findings so
the autonomous remediator's filter is mechanical (skip ``principal.governor``
findings) rather than YAML-only routing. When the set of rules that need a
governor's architectural judgment changes, this is the module that changes.

LAYER: will/workers — collaborator of AuditViolationSensor. Pure lookup:
no IO, no side effects.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)


# ADR-095 D4: architectural-judgment rules carry a routing marker on
# their findings so the autonomous remediator's filter is mechanical
# (skip principal.governor findings) rather than YAML-only routing.
# Per ADR-068 principal role taxonomy.
#
# The marker is ``route_to``, not ``resolution_authority`` (#943): that name
# belongs only to payload.resolution.resolution_authority, the record of under
# whose authority a finding was closed, which re-arms exhausted remediation
# caps (ADR-104 D9 amended). A routing hint must never be mistakable for it.
#
# Extended 2026-06-06 to include architecture.mind.no_execution_semantics
# (ADR-095 D6 sibling case): llm_gate rule, same yes/no-verdict-at-scale
# pattern that motivated D6's deferral of modularity.unix_philosophy.
_ARCHITECTURAL_JUDGMENT_RULES: frozenset[str] = frozenset(
    {
        "modularity.needs_split",
        "modularity.class_too_large",
        "modularity.needs_refactor",
        "modularity.unix_philosophy",
        "purity.no_ast_duplication",
        "purity.no_semantic_duplication",
        "purity.no_orphan_files",
        "architecture.mind.no_execution_semantics",
    }
)


def _route_to(rule_id: str) -> str | None:
    """The principal a finding for *rule_id* is routed to, or None (ADR-095 D4)."""
    if rule_id in _ARCHITECTURAL_JUDGMENT_RULES:
        return "principal.governor"
    return None
