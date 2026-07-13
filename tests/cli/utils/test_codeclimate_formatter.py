"""F-10.P2 — CodeClimate JSON formatter tests.

Guards the severity-to-CodeClimate-severity mapping, the fingerprint
stability, and the format_payload output structure consumed by GitLab's
`artifacts: reports: codequality:` key.

Finding dict shape matches ``AuditFinding.as_dict()``: ``check_id``,
``severity``, ``message``, ``file_path``, ``line_number``.
"""

from __future__ import annotations

import json

from cli.utils.codeclimate_formatter import (
    fingerprint,
    format_finding,
    format_payload,
    severity_to_codeclimate,
)
from shared.models import AuditFinding, AuditSeverity


def test_blocking_maps_to_blocker() -> None:
    assert severity_to_codeclimate("blocking") == "blocker"


def test_block_maps_to_blocker() -> None:
    assert severity_to_codeclimate("block") == "blocker"


def test_high_maps_to_critical() -> None:
    assert severity_to_codeclimate("high") == "critical"


def test_medium_maps_to_major() -> None:
    assert severity_to_codeclimate("medium") == "major"


def test_low_maps_to_minor() -> None:
    assert severity_to_codeclimate("low") == "minor"


def test_info_maps_to_info() -> None:
    assert severity_to_codeclimate("info") == "info"


def test_unknown_severity_defaults_to_info() -> None:
    """Unknown severities fall back to info — visible but non-blocking."""
    assert severity_to_codeclimate("invented-level") == "info"


def test_fingerprint_is_stable() -> None:
    """Same inputs always produce the same fingerprint (GitLab dedup relies on this)."""
    fp1 = fingerprint("my.rule", "src/foo.py", 42)
    fp2 = fingerprint("my.rule", "src/foo.py", 42)
    assert fp1 == fp2


def test_fingerprint_differs_by_rule() -> None:
    fp1 = fingerprint("rule.a", "src/foo.py", 10)
    fp2 = fingerprint("rule.b", "src/foo.py", 10)
    assert fp1 != fp2


def test_fingerprint_differs_by_line() -> None:
    fp1 = fingerprint("my.rule", "src/foo.py", 10)
    fp2 = fingerprint("my.rule", "src/foo.py", 11)
    assert fp1 != fp2


def test_format_finding_required_fields() -> None:
    finding = {
        "check_id": "my.rule.id",
        "severity": "high",
        "message": "Something is wrong",
        "file_path": "src/body/foo.py",
        "line_number": 37,
    }
    result = format_finding(finding)
    assert result["type"] == "issue"
    assert result["check_name"] == "my.rule.id"
    assert "high" in result["description"]
    assert "Something is wrong" in result["description"]
    assert result["severity"] == "critical"
    assert result["location"]["path"] == "src/body/foo.py"
    assert result["location"]["lines"]["begin"] == 37
    assert "fingerprint" in result


def test_format_finding_no_file_uses_dot_path() -> None:
    """Findings without a file path anchor to '.' so GitLab still has a path."""
    finding = {
        "check_id": "rule.id",
        "severity": "info",
        "message": "context-level finding",
        "file_path": None,
        "line_number": None,
    }
    result = format_finding(finding)
    assert result["location"]["path"] == "."
    assert result["location"]["lines"]["begin"] == 1


def test_format_finding_none_sentinel_file_treated_as_no_file() -> None:
    """'none' string is the legacy sentinel for findings without a file location."""
    finding = {
        "check_id": "rule.id",
        "severity": "info",
        "message": "x",
        "file_path": "none",
        "line_number": None,
    }
    result = format_finding(finding)
    assert result["location"]["path"] == "."


def test_format_payload_empty_findings() -> None:
    """Empty finding list produces a valid empty JSON array."""
    payload = {"findings": [], "verdict": "PASS", "passed": True}
    output = format_payload(payload)
    assert json.loads(output) == []


def test_format_payload_returns_json_array() -> None:
    payload = {
        "findings": [
            {
                "check_id": "arch.rule",
                "severity": "blocking",
                "message": "import violation",
                "file_path": "src/body/foo.py",
                "line_number": 5,
            }
        ],
        "verdict": "FAIL",
        "passed": False,
    }
    output = format_payload(payload)
    issues = json.loads(output)
    assert isinstance(issues, list)
    assert len(issues) == 1
    assert issues[0]["severity"] == "blocker"


def test_format_payload_skipped_rules_not_included() -> None:
    """Skipped rules have no file/line — they must not appear in CodeClimate output."""
    payload = {
        "findings": [],
        "skipped_rules": [{"rule_id": "llm.gate", "reason": "no DB"}],
        "verdict": "PASS",
        "passed": True,
    }
    output = format_payload(payload)
    assert json.loads(output) == []


def test_format_payload_real_audit_finding_shape() -> None:
    """Round-trip through AuditFinding.as_dict() — guards against key-name drift."""
    af = AuditFinding(
        check_id="architecture.boundary.test",
        message="Direct import",
        file_path="src/will/foo.py",
        line_number=12,
        severity=AuditSeverity.BLOCK,
    )
    finding_dict = af.as_dict()
    result = format_finding(finding_dict)
    assert result["severity"] == "blocker"
    assert result["location"]["path"] == "src/will/foo.py"
    assert result["location"]["lines"]["begin"] == 12
