# src/mind/governance/finding_processor.py

"""
Core logic for processing and downgrading audit findings.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence

from mind.governance.entry_point_policy import EntryPointAllowList


# ID: f2778ec7-aa0d-4025-90c1-9af82c1f27fb
def safe_symbol_meta(
    symbol_index: Mapping[str, Mapping[str, object]], symbol_key: str
) -> Mapping[str, object]:
    """Safely retrieve symbol metadata from index."""
    return symbol_index.get(symbol_key, {}) or {}


# ID: 9875bf96-ccab-4a2a-bcd0-374da32f634e
def process_findings_with_downgrade(
    findings: Sequence[MutableMapping[str, object]],
    symbol_index: Mapping[str, Mapping[str, object]],
    allow_list: EntryPointAllowList,
    dead_rule_ids: Iterable[str],
    downgrade_to: str = "info",
) -> tuple[list[MutableMapping[str, object]], list[dict[str, object]]]:
    """
    Process findings and downgrade severity for allowed entry points.

    Args:
        findings: List of audit findings to process
        symbol_index: Mapping of symbol keys to their metadata
        allow_list: Entry point types that should be downgraded
        dead_rule_ids: Rule IDs that identify dead-public-symbol findings
        downgrade_to: Target severity level for downgrade

    Returns:
        Tuple of (processed_findings, auto_ignored_items)
    """
    dead_ids = {r.strip() for r in dead_rule_ids if r and r.strip()}
    processed: list[MutableMapping[str, object]] = []
    auto_ignored: list[dict[str, object]] = []

    for finding in findings:
        rule_id = str(finding.get("rule_id", "") or "")
        symbol_key = str(finding.get("symbol_key", "") or "")
        severity = str(finding.get("severity", "") or "").lower()

        if rule_id in dead_ids and symbol_key:
            meta = safe_symbol_meta(symbol_index, symbol_key)
            ep_type = str(meta.get("entry_point_type", "") or "")
            pattern_name = str(meta.get("pattern_name", "") or "")
            justification = str(meta.get("entry_point_justification", "") or "")

            if ep_type in allow_list:
                # Downgrade severity only if current is higher
                if severity in {"error", "warn"}:
                    finding["severity"] = downgrade_to

                auto_ignored.append(
                    {
                        "symbol_key": symbol_key,
                        "entry_point_type": ep_type,
                        "pattern_name": pattern_name or None,
                        "justification": justification or None,
                        "original_rule_id": rule_id,
                        "downgraded_to": finding.get("severity"),
                    }
                )

        processed.append(finding)

    return processed, auto_ignored
