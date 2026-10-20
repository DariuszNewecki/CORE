# src/will/autonomy/violation_remediator_grouping.py
"""
Pure grouping helpers for ViolationRemediatorWorker.

Split out of ``will/workers/violation_remediator.py`` (modularity.needs_split)
with no behavior change: entry-id extraction, the rule list of a finding set,
the (action, file) grouping of open findings per ADR-035 D1, and the
DELEGATE log lines. No I/O beyond logging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2b15e52c-376a-43fc-a3af-d4f5405a5399
def entry_id(finding: dict[str, Any]) -> str:
    """Extract blackboard entry id ('id' or 'entry_id'); raise on contract violation."""
    value = finding.get("id") or finding.get("entry_id")
    if value is None:
        raise ValueError(f"Finding has neither 'id' nor 'entry_id': {finding!r}")
    return str(value)


# ID: f88cae17-98bb-4727-bab0-95e1ac69cb01
def rules_of(findings: list[dict[str, Any]]) -> list[str]:
    """Deduplicated rule list from findings — used in completion report."""
    return list(
        {
            f["payload"].get("check_id") or f["payload"].get("rule", "unknown")
            for f in findings
        }
    )


@dataclass
# ID: 99ff07af-0317-484a-a3de-f3365107318c
class FindingGroups:
    """Open findings sorted by what the remediation map says to do with them."""

    action_groups: dict[tuple[str, str | None], list[dict[str, Any]]] = field(
        default_factory=dict
    )
    ref_kinds: dict[str, str] = field(default_factory=dict)
    unmappable: list[dict[str, Any]] = field(default_factory=list)
    delegate: list[dict[str, Any]] = field(default_factory=list)


# ID: b12b3fed-9276-4305-ad06-f3539050d33a
def group_findings(
    open_findings: list[dict[str, Any]], remediation_map: dict
) -> FindingGroups:
    """Group findings by (ref_id, file_path) per ADR-035 D1.

    A flow targets no file, so its key is (ref_id, None). A DELEGATE entry
    goes to ``delegate`` with its map entry stashed under ``_map_entry``; a
    rule with no mapping goes to ``unmappable``.
    """
    groups = FindingGroups()
    for finding in open_findings:
        rule = finding["payload"].get("check_id") or finding["payload"].get("rule", "")
        entry = remediation_map.get(rule)

        if entry and entry.get("status") == "DELEGATE":
            finding["_map_entry"] = entry
            groups.delegate.append(finding)
        elif entry:
            ref_id = entry["ref_id"]
            ref_kind = entry["ref_kind"]
            if ref_kind == "flow":
                key = (ref_id, None)
            else:
                file_path = finding["payload"].get("file_path") or None
                key = (ref_id, file_path)
            groups.action_groups.setdefault(key, []).append(finding)
            groups.ref_kinds[ref_id] = ref_kind
        else:
            groups.unmappable.append(finding)
            logger.debug(
                "ViolationRemediatorWorker: no remediation mapping for rule '%s'",
                rule,
            )
    return groups


# ID: 0bfdd353-35af-4d56-8ce0-d3cd6e9a2c44
def log_delegated(delegate: list[dict[str, Any]]) -> None:
    """One [DELEGATE] log line per finding that needs a human decision."""
    for finding in delegate:
        rule = finding["payload"].get("check_id") or finding["payload"].get(
            "rule", "unknown"
        )
        file_path = finding["payload"].get("file_path", "unknown")
        map_entry = finding.get("_map_entry", {})
        description = map_entry.get("description", "")
        logger.info(
            "[DELEGATE] %s -> HUMAN REQUIRED\n"
            "           File: %s\n"
            "           Decision needed: %s\n"
            "           Resolve with: core-admin workers blackboard --reopen %s",
            rule,
            file_path,
            description,
            finding.get("id") or finding.get("entry_id"),
        )
