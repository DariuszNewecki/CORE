"""F-10.2 — GitHub Actions annotation formatter tests.

Guards the severity-to-channel mapping and the GH workflow-command
syntax. A regression in either would break the F-10 user-visible
surface — findings in the workflow log are not enough; the PR diff
view inline annotations are what reviewers see.
"""

from __future__ import annotations

from cli.utils.annotation_formatter import (
    format_finding,
    format_payload,
    format_skipped_rule,
    severity_to_channel,
)


def test_blocking_severity_maps_to_error_channel() -> None:
    """blocking -> error -> required-check failure -> merge-block."""
    assert severity_to_channel("blocking") == "error"


def test_high_severity_maps_to_error_channel() -> None:
    """high -> error. Matches the default --severity floor."""
    assert severity_to_channel("high") == "error"


def test_medium_severity_maps_to_warning_channel() -> None:
    """medium -> warning. Visible in PR diff but non-blocking."""
    assert severity_to_channel("medium") == "warning"


def test_low_severity_maps_to_notice_channel() -> None:
    """low -> notice. Informational."""
    assert severity_to_channel("low") == "notice"


def test_info_severity_maps_to_notice_channel() -> None:
    """info -> notice. Informational."""
    assert severity_to_channel("info") == "notice"


def test_unknown_severity_defaults_to_notice() -> None:
    """Safer default: surface as notice (visible, non-blocking) rather than drop.

    A future severity value added without the formatter being updated
    should still appear in the PR; silent dropping would hide
    regressions.
    """
    assert severity_to_channel("brand-new-severity") == "notice"


def test_format_finding_produces_workflow_command_line() -> None:
    """Standard GH workflow-command format: ::CHANNEL key=val,key=val::MESSAGE"""
    finding = {
        "rule_id": "test.rule",
        "file": "src/foo.py",
        "line": 42,
        "severity": "high",
        "message": "violation occurred",
    }
    line = format_finding(finding)
    assert line.startswith("::error ")
    assert "file=src/foo.py" in line
    assert "line=42" in line
    assert "test.rule" in line
    assert line.endswith("::violation occurred")


def test_format_finding_url_encodes_special_chars() -> None:
    """Newlines / %/CR in message must be URL-encoded or the parser breaks.

    Per GH workflow-commands docs: %0A (newline), %0D (CR), %25 (percent).
    A raw newline would terminate the workflow-command and the rest of
    the message would be interpreted as a new command (or just lost).
    """
    finding = {
        "rule_id": "r",
        "file": "f.py",
        "line": 1,
        "severity": "low",
        "message": "line1\nline2 100% bad",
    }
    line = format_finding(finding)
    assert "\n" not in line.replace("\n", "", 1) or line.count("\n") == 0
    assert "%0A" in line  # newline encoded
    assert "%25" in line  # percent encoded


def test_format_skipped_rule_produces_notice_without_file_line() -> None:
    """Skipped rules surface to the workflow log as notices.

    No file/line — they don't apply to a specific source location.
    Operator sees the F-10.1a honesty signal in the workflow output
    without diff-view noise.
    """
    skipped = {
        "rule_id": "graph.unreachable",
        "engine": "knowledge_gate",
        "reason": "requires knowledge graph; not available in stateless mode",
    }
    line = format_skipped_rule(skipped)
    assert line.startswith("::notice ")
    assert "graph.unreachable" in line
    assert "knowledge graph" in line
    assert "file=" not in line
    assert "line=" not in line


def test_format_payload_emits_findings_then_skips_then_summary() -> None:
    """Output order is contract: findings → skipped → summary.

    A consumer that truncates at the first line still gets useful
    finding data. Summary at the end lets the operator see counts in a
    glance at the workflow log tail.
    """
    payload = {
        "verdict": "FAIL",
        "passed": False,
        "findings": [
            {
                "rule_id": "r.1",
                "file": "src/x.py",
                "line": 1,
                "severity": "high",
                "message": "bad",
            },
            {
                "rule_id": "r.2",
                "file": "src/y.py",
                "line": 2,
                "severity": "medium",
                "message": "less-bad",
            },
        ],
        "skipped_rules": [
            {"rule_id": "skip.1", "engine": "knowledge_gate", "reason": "needs graph"},
        ],
    }
    output = format_payload(payload)
    lines = [ln for ln in output.split("\n") if ln]
    assert len(lines) == 4  # 2 findings + 1 skip + 1 summary
    assert lines[0].startswith("::error ")
    assert "r.1" in lines[0]
    assert lines[1].startswith("::warning ")
    assert "r.2" in lines[1]
    assert lines[2].startswith("::notice ")
    assert "skip.1" in lines[2]
    assert lines[3].startswith("::notice ")
    assert "summary" in lines[3].lower()
    assert "verdict=FAIL" in lines[3]


def test_format_payload_handles_empty_results() -> None:
    """Empty findings + empty skipped still emits a summary line.

    A clean run must produce some output so the CI consumer doesn't
    interpret an empty stdout as a missing artifact.
    """
    payload = {
        "verdict": "PASS",
        "passed": True,
        "findings": [],
        "skipped_rules": [],
    }
    output = format_payload(payload)
    lines = [ln for ln in output.split("\n") if ln]
    assert len(lines) == 1
    assert "verdict=PASS" in lines[0]
    assert "findings=0" in lines[0]
    assert "skipped_rules=0" in lines[0]


def test_format_payload_handles_missing_optional_fields() -> None:
    """Missing 'findings' / 'skipped_rules' keys default to empty lists.

    Defensive against early prototypes or non-stateless payloads that
    might be threaded through accidentally.
    """
    payload = {"verdict": "UNKNOWN"}
    output = format_payload(payload)
    lines = [ln for ln in output.split("\n") if ln]
    assert len(lines) == 1
    assert "verdict=UNKNOWN" in lines[0]
