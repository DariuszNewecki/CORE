"""Cold room 2026-10-09: `code audit --offline` displayed a regex match as
"needs human" (evidence class dropped) and "Coverage 0.0%" (unmeasured stats
hard-coded to 0). Display only; verdicts, exit codes and JSON are unchanged."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from cli.commands.check import formatters
from cli.logic import audit_renderer
from cli.logic.audit_renderer import AuditStats, render_overview, to_audit_finding
from cli.resources.code import audit as audit_cmd
from shared.models import AuditSeverity, EvidenceClass


def _raw_violation(**overrides) -> dict:
    raw = {
        "check_id": "starter.no_bare_except",
        "severity": "block",
        "evidence_class": "proven",
        "message": "Forbidden Content [Line 9]",
        "file_path": "src/myproject/risky.py",
        "line_number": 9,
        "context": {},
    }
    raw.update(overrides)
    return raw


# ID: 4acf35f0-a4ca-48fa-a796-d59c1631327d
def test_to_audit_finding_keeps_evidence_class() -> None:
    finding = to_audit_finding(_raw_violation())
    assert finding.severity is AuditSeverity.BLOCK
    assert finding.evidence_class is EvidenceClass.PROVEN


@pytest.mark.parametrize("value", [None, "", "certain"])
# ID: 6d6dbc5a-a337-4612-a4b6-bb222218a5ff
def test_to_audit_finding_missing_or_unknown_evidence_is_attested(value) -> None:
    raw = _raw_violation(evidence_class=value)
    if value is None:
        del raw["evidence_class"]
    assert to_audit_finding(raw).evidence_class is EvidenceClass.ATTESTED


# ID: 4b4044e5-14c8-4bf5-a6eb-6baa506de88a
def test_unmeasured_stats_render_as_na_not_zero() -> None:
    buf = io.StringIO()
    stats = AuditStats(
        total_rules=4,
        executed_rules=4,
        coverage_percent=None,
        total_declared_rules=4,
        crashed_rules=0,
        unmapped_rules=None,
        effective_coverage_percent=None,
        context_level_rules=None,
        per_file_rules=None,
    )
    render_overview(Console(file=buf, width=200), [], stats, 0.1, True, "PASS")
    out = buf.getvalue()
    assert "Coverage: n/a" in out
    assert "Effective coverage: n/a" in out
    assert "Unmapped: n/a" in out
    assert "Crashed: 0" in out
    assert "coverage: 0.0%" not in out.lower()


# ID: 0da43301-d9d1-4627-9057-4199da7ab7a0
def test_measured_stats_still_render_numbers() -> None:
    buf = io.StringIO()
    stats = AuditStats(coverage_percent=87.5, effective_coverage_percent=80.0)
    render_overview(Console(file=buf, width=200), [], stats, 0.1, True, "PASS")
    out = buf.getvalue()
    assert "Coverage: 87.5%" in out
    assert "Effective coverage: 80.0%" in out


# ID: 629232cc-d79d-445c-a167-e2e788a594d4
def test_offline_summary_shows_block_proven_and_no_false_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buf = io.StringIO()
    shared_console = Console(file=buf, width=200)
    monkeypatch.setattr(audit_cmd, "console", shared_console)
    monkeypatch.setattr(formatters, "console", shared_console)
    monkeypatch.setattr(audit_renderer, "console", shared_console)
    result = {
        "verdict": "FAIL",
        "passed": False,
        "stats": {
            "total_rules": 4,
            "runnable_rules": 4,
            "executed_rules": 4,
            "failed_rules": 0,
        },
        "findings": [_raw_violation()],
        "skipped_rules": [],
        "duration_sec": 0.2,
    }
    audit_cmd._render_text_summary(result, AuditSeverity.INFO)
    out = buf.getvalue()
    row = next(line for line in out.splitlines() if "starter.no_bare_except" in line)
    assert "BLOCK" in row and "proven" in row
    assert "ERROR" not in row and "needs human" not in row
    assert "Coverage: n/a" in out
    assert "coverage: 0.0%" not in out.lower()
