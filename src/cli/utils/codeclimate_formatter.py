# src/cli/utils/codeclimate_formatter.py

"""F-10.P2 — CodeClimate JSON formatter for GitLab MR quality reports.

Renders the F-10.1a stateless-audit payload as a CodeClimate-compatible
JSON array so GitLab can surface findings inline in merge request diff view
via the `report:codequality` artifact mechanism.

CodeClimate format reference:
https://github.com/codeclimate/platform/blob/master/spec/analyzers/SPEC.md

Each finding maps to one CodeClimate issue object. The format is consumed
by GitLab's `artifacts: reports: codequality:` key and appears in the MR
UI's "Code Quality" tab with severity indicators and file/line links.

Severity mapping (CORE → CodeClimate):

| CORE severity | CodeClimate severity | GitLab badge colour  |
|---------------|---------------------|----------------------|
| blocking      | blocker             | red (blocks MR)      |
| block         | blocker             | red (blocks MR)      |
| high          | critical            | red                  |
| medium        | major               | orange               |
| low           | minor               | yellow               |
| info          | info                | blue                 |

Unknown severities fall back to ``info`` — visible but non-blocking.

The ``fingerprint`` field is a stable per-finding identity signal used by
GitLab to detect which findings are new vs. pre-existing. It is derived
from (rule_id, file_path, line_number) so the same violation in the same
place across runs produces the same fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SEVERITY_MAP: dict[str, str] = {
    "blocking": "blocker",
    "block": "blocker",
    "high": "critical",
    "medium": "major",
    "low": "minor",
    "info": "info",
}

_CATEGORY = "Bug Risk"


# ID: 76e10f7c-3497-4991-bf0d-a92821685f47
def severity_to_codeclimate(severity: str) -> str:
    """Map a CORE severity string to a CodeClimate severity level.

    Unknown severities fall back to ``info`` (visible, non-blocking).
    """
    return _SEVERITY_MAP.get(severity.lower(), "info")


# ID: 2f5248bb-0b6d-4094-a758-41bb864428e4
def fingerprint(rule_id: str, file_path: str, line_number: int | None) -> str:
    """Produce a stable per-finding fingerprint for CodeClimate dedup.

    GitLab uses the fingerprint to determine whether a finding is new or
    pre-existing. A deterministic hash of (rule_id, file_path, line_number)
    ensures the same violation produces the same fingerprint across runs.
    """
    key = f"{rule_id}:{file_path or ''}:{line_number or 0}"
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()


# ID: 64a944e9-f78d-464d-b7eb-da171b11a6ff
def format_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Convert one F-10.1a finding dict to a CodeClimate issue object.

    Required CodeClimate fields: ``type``, ``check_name``, ``description``,
    ``categories``, ``location``, ``severity``, ``fingerprint``.
    """
    rule_id = finding.get("check_id") or "unknown"
    severity_str = str(finding.get("severity", "info"))
    message = str(finding.get("message") or rule_id)
    file_path = finding.get("file_path") or ""
    if file_path == "none":
        file_path = ""
    line_no = finding.get("line_number")

    location: dict[str, Any]
    if file_path:
        location = {
            "path": file_path,
            "lines": {"begin": line_no if line_no else 1},
        }
    else:
        # Findings without a file location anchor to repo root at line 1.
        # GitLab requires a path; using "." is the least-surprising fallback.
        location = {"path": ".", "lines": {"begin": 1}}

    return {
        "type": "issue",
        "check_name": rule_id,
        "description": f"[{severity_str}] {message}",
        "content": {"body": f"Rule `{rule_id}` reported: {message}"},
        "categories": [_CATEGORY],
        "location": location,
        "severity": severity_to_codeclimate(severity_str),
        "fingerprint": fingerprint(rule_id, file_path, line_no),
    }


# ID: bb55c39a-0840-4f86-b3f2-f1f0f42b88b7
def format_payload(payload: dict[str, Any]) -> str:
    """Render the full F-10.1a payload as a CodeClimate JSON array.

    Returns a JSON string (with trailing newline) containing one issue
    object per finding. Suitable for direct write to stdout from the
    CLI's --format=codeclimate path.

    Skipped rules are NOT included in the CodeClimate output — they carry
    no file/line location and would appear as phantom issues in the MR UI.
    The ``--format=json`` path remains available for operators who want
    to inspect the skipped-rule list.

    An empty result (no findings) produces a valid empty array ``[]\n``
    which GitLab interprets as "no quality issues found".
    """
    findings = payload.get("findings", []) or []
    issues = [format_finding(f) for f in findings]
    return json.dumps(issues, indent=2) + "\n"


__all__ = [
    "fingerprint",
    "format_finding",
    "format_payload",
    "severity_to_codeclimate",
]
