# src/shared/utils/audit_grouping.py
## src/shared/utils/audit_grouping.py
"""Utilities for grouping and analyzing audit findings."""

from collections import defaultdict

from shared.models import AuditFinding, AuditSeverity
from shared.models.audit_rendering import SeverityGroup


SEVERITY_ORDER: dict[AuditSeverity, int] = {
    AuditSeverity.ERROR: 3,  # highest / blocking
    AuditSeverity.WARNING: 2,
    AuditSeverity.INFO: 1,  # or 0 if you want INFO lowest
    # AuditSeverity.CRITICAL: 4,  # ← removed, doesn't exist
    # AuditSeverity.HIGH:     3,
    # AuditSeverity.MEDIUM:   2,
    # AuditSeverity.LOW:      1,
}


# ID: 9b328c94-6552-41e2-9a2e-46419693f6da
def group_findings(findings: list[AuditFinding]) -> list[SeverityGroup]:
    """Group findings by severity and return sorted list of groups (descending severity).

    Returns new lists/tuples; no in-place mutation.
    """
    groups_dict: dict[AuditSeverity, list[AuditFinding]] = defaultdict(list)
    for finding in findings:
        groups_dict[finding.severity].append(finding)

    sorted_severities = sorted(
        groups_dict,
        key=lambda s: SEVERITY_ORDER.get(s, -1),
        reverse=True,
    )

    groups: list[SeverityGroup] = []
    for sev in sorted_severities:
        findings_list = groups_dict[sev]
        groups.append(SeverityGroup(sev, tuple(findings_list)))
    return groups


# ID: f845871b-2720-4de3-a92d-29c7d14f9682
def get_max_severity(groups: list[SeverityGroup]) -> AuditSeverity | None:
    """Get highest severity from non-empty groups."""
    non_empty_groups = [g for g in groups if g.count > 0]
    if not non_empty_groups:
        return None
    max_group = max(non_empty_groups, key=lambda g: SEVERITY_ORDER.get(g.severity, -1))
    return max_group.severity
