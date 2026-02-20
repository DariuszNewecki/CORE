# src/mind/governance/audit_postprocessor.py
"""
Post-processing utilities for Constitutional Auditor findings.

CONSTITUTIONAL ALIGNMENT (V2.3.0):
- Purified: No Body-layer dependencies or filesystem execution.
- Returns data structures to the caller for enforcement.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence

from mind.governance.entry_point_policy import EntryPointAllowList
from mind.governance.finding_processor import process_findings_with_downgrade


# ID: d32e09f5-a660-4d69-8fe9-10e91dae70ca
def apply_entry_point_downgrade(
    *,
    findings: Sequence[MutableMapping[str, object]],
    symbol_index: Mapping[str, Mapping[str, object]],
    allow_list: EntryPointAllowList | None = None,
    dead_rule_ids: Iterable[str] = ("dead_public_symbol", "dead-public-symbol"),
    downgrade_to: str = "info",
) -> tuple[list[MutableMapping[str, object]], list[dict[str, object]]]:
    """Pure Logic: Identifies entry points and returns downgraded findings."""
    allow = allow_list or EntryPointAllowList.default()

    return process_findings_with_downgrade(
        findings=findings,
        symbol_index=symbol_index,
        allow_list=allow,
        dead_rule_ids=dead_rule_ids,
        downgrade_to=downgrade_to,
    )
