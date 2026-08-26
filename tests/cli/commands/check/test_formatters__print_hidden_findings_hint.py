# tests/cli/commands/check/test_formatters__print_hidden_findings_hint.py

"""Tests for print_hidden_findings_hint (src/cli/commands/check/formatters.py).

Covers the gap that motivated it: the existing "Run with '--verbose'" hint
in print_summary_findings only applies to findings already at/above the
--severity floor. Findings below the floor never appear in any itemized
view (summary or verbose) even though they count toward the Audit Overview
severity totals — this hint is the only place that tells the operator they
exist and how to see them.
"""

from __future__ import annotations

import pytest

from cli.commands.check.formatters import print_hidden_findings_hint
from shared.models import AuditFinding, AuditSeverity


def _finding(severity: AuditSeverity, check_id: str = "some.rule") -> AuditFinding:
    return AuditFinding(
        check_id=check_id,
        severity=severity,
        message="irrelevant",
        file_path="src/example.py",
    )


def test_hint_printed_when_findings_are_hidden_below_floor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """3 INFO findings filtered out under a HIGH floor → hint names the count."""
    all_findings = [
        _finding(AuditSeverity.HIGH),
        _finding(AuditSeverity.INFO),
        _finding(AuditSeverity.INFO),
        _finding(AuditSeverity.INFO),
    ]
    filtered = [f for f in all_findings if f.severity >= AuditSeverity.HIGH]

    print_hidden_findings_hint(all_findings, filtered, AuditSeverity.HIGH)

    captured = capsys.readouterr()
    normalized = " ".join(captured.out.split())
    assert "3 additional finding(s)" in normalized
    assert "--severity info --verbose" in normalized


def test_no_hint_when_nothing_is_hidden(capsys: pytest.CaptureFixture[str]) -> None:
    """filtered == all_findings → nothing below the floor, no hint."""
    all_findings = [_finding(AuditSeverity.HIGH), _finding(AuditSeverity.BLOCK)]

    print_hidden_findings_hint(all_findings, all_findings, AuditSeverity.HIGH)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_no_hint_when_floor_is_already_info(capsys: pytest.CaptureFixture[str]) -> None:
    """--severity info is the lowest floor — nothing left to reveal."""
    all_findings = [_finding(AuditSeverity.INFO), _finding(AuditSeverity.HIGH)]

    print_hidden_findings_hint(all_findings, all_findings, AuditSeverity.INFO)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_hint_printed_even_when_filtered_findings_is_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """All findings are below the floor — filtered is empty, hint still fires."""
    all_findings = [_finding(AuditSeverity.INFO), _finding(AuditSeverity.INFO)]
    filtered: list[AuditFinding] = []

    print_hidden_findings_hint(all_findings, filtered, AuditSeverity.HIGH)

    captured = capsys.readouterr()
    assert "2 additional finding(s)" in captured.out
