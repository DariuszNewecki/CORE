# src/cli/utils/annotation_formatter.py

"""F-10.2 — GitHub Actions workflow-command annotation formatter.

Renders the F-10.1a stateless-audit payload as GitHub Actions
workflow-command lines so findings surface inline in PR diff view
(next to the offending line) rather than only in the workflow log.

Format per GitHub Actions documentation:

    ::error file=PATH,line=N,col=N::MESSAGE
    ::warning file=PATH,line=N,col=N::MESSAGE
    ::notice file=PATH,line=N,col=N::MESSAGE

ADR-085 §D5 lists "PR annotations + merge-blocking demonstrated
against a real external repo" as the F-10 exit criterion. The
annotation channel is the user-visible surface of the gate — findings
only in the workflow log are effectively invisible in a developer's
PR review flow.

Severity-to-channel mapping (constitutional contract):

| CORE severity | GH channel | Merge-block? | Why                              |
|---------------|------------|--------------|----------------------------------|
| blocking      | error      | yes          | gate's whole point               |
| high          | error      | yes          | parse_min_severity default       |
| medium        | warning    | no           | visible in PR, doesn't block     |
| low           | notice     | no           | informational                    |
| info          | notice     | no           | informational                    |

Skipped rules (from F-10.1a's `skipped_rules` field) are emitted as
notices so the operator sees them in the workflow log, but they do not
appear inline in the diff (no file/line). This preserves the honesty
commitment from F-10.1a — degraded coverage is surfaced, not silent.
"""

from __future__ import annotations

from typing import Any


_SEVERITY_TO_CHANNEL: dict[str, str] = {
    "blocking": "error",
    "block": "error",
    "high": "error",
    "medium": "warning",
    "low": "notice",
    "info": "notice",
}

# The 'error' channel is what GitHub uses to fail required status
# checks; merge-blocking is keyed off this. Documented here so a future
# maintainer can audit the merge-block surface in one place.
_MERGE_BLOCKING_CHANNELS: frozenset[str] = frozenset({"error"})


# ID: 496df0ee-c556-41ba-b894-05e5979b2f64
def severity_to_channel(severity: str) -> str:
    """Map a CORE severity string to a GH annotation channel.

    Unknown severities fall back to ``notice`` (visible but non-blocking).
    This is the safer default: a misclassified finding still surfaces
    rather than getting silently swallowed.
    """
    return _SEVERITY_TO_CHANNEL.get(severity.lower(), "notice")


# ID: 9922cc55-939c-435d-94a3-74af7e048f04
def format_finding(finding: dict[str, Any]) -> str:
    """Format a single finding as one GH workflow-command line.

    Newlines and ``%``/``\\r`` characters in the message are URL-encoded
    per GitHub's escaping rules; otherwise a multi-line message breaks
    the workflow-command parser and the annotation never renders.
    """
    severity = str(finding.get("severity", "info"))
    channel = severity_to_channel(severity)

    file_path = finding.get("file", "")
    line_no = finding.get("line", 1) or 1
    raw_message = str(finding.get("message", "") or finding.get("rule_id", ""))
    rule_id = finding.get("rule_id", "")
    title = f"{rule_id} [{severity}]" if rule_id else severity

    # GH's workflow-command parser breaks on raw newlines and on the
    # literal characters % \r \n inside the message. Encode per the GH
    # documentation: %25 %0D %0A.
    safe_message = (
        raw_message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    )
    safe_title = title.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    parts = [f"file={file_path}", f"line={line_no}", f"title={safe_title}"]
    return f"::{channel} {','.join(parts)}::{safe_message}"


# ID: 319d626b-b926-4ab0-abf0-9df4cb07419a
def format_skipped_rule(skipped: dict[str, str]) -> str:
    """Format one skipped-rule entry as a GH notice (no file/line).

    Skipped rules surface as workflow-log notices so the operator sees
    the F-10.1a honesty signal (which rules ran vs. were skipped) but
    they do not appear in the PR diff. CI users learn about reduced
    coverage from the workflow output, not from the absence of
    annotations.
    """
    rule_id = skipped.get("rule_id", "")
    reason = skipped.get("reason", "skipped").replace("%", "%25")
    return f"::notice title=Rule skipped: {rule_id}::{reason}"


# ID: 2bc4a2c5-b119-40d1-88b4-27ee32978c5d
def format_payload(payload: dict[str, Any]) -> str:
    """Render the full F-10.1a payload as GH workflow-command lines.

    Returns a newline-joined string; trailing newline included so the
    last annotation parses correctly. Suitable for direct write to
    stdout from the CLI's --format=github-annotations path.

    Output order:
    1. One line per finding (file/line/severity/message)
    2. One line per skipped rule (workflow-log notice, no file/line)
    3. One summary line on stderr-style notice (verdict + counts)

    The summary appears last so a downstream consumer that truncates at
    the first annotation still sees per-finding lines first.
    """
    lines: list[str] = []
    findings = payload.get("findings", []) or []
    for finding in findings:
        lines.append(format_finding(finding))

    skipped = payload.get("skipped_rules", []) or []
    for entry in skipped:
        lines.append(format_skipped_rule(entry))

    verdict = payload.get("verdict", "UNKNOWN")
    finding_count = len(findings)
    skipped_count = len(skipped)
    summary = (
        f"CORE audit (stateless): verdict={verdict} "
        f"findings={finding_count} skipped_rules={skipped_count}"
    )
    lines.append(f"::notice title=CORE audit summary::{summary}")

    return "\n".join(lines) + "\n"


__all__ = [
    "format_finding",
    "format_payload",
    "format_skipped_rule",
    "severity_to_channel",
]
