"""ADR-098 D3: `--verbose` lists the sample issues behind an aggregate
quality-gate finding, with a footer when the samples are truncated; and the
offline path honours `--verbose` instead of silently ignoring it."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from cli.commands.check import formatters
from cli.logic import audit_renderer
from cli.resources.code import audit as audit_cmd
from shared.models import AuditFinding, AuditSeverity


def _aggregate(issue_count: int, n_samples: int) -> AuditFinding:
    return AuditFinding(
        "purity.no_dead_code",
        AuditSeverity.MEDIUM,
        f"{issue_count} dead-code candidate(s) in src/a.py",
        file_path="src/a.py",
        context={
            "tool": "vulture",
            "issue_count": issue_count,
            "sample_issues": [
                f"src/a.py:{i}: unused function 'f{i}'" for i in range(n_samples)
            ],
        },
    )


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buf = io.StringIO()
    monkeypatch.setattr(formatters, "console", Console(file=buf, width=200))
    return buf


# ID: 2b45cd69-232a-4994-8895-1adf4b1299a7
def test_verbose_lists_samples_with_truncation_footer(captured: io.StringIO) -> None:
    formatters.print_verbose_findings([_aggregate(issue_count=25, n_samples=10)])
    out = captured.getvalue()
    assert "src/a.py:0: unused function 'f0'" in out
    assert "src/a.py:9: unused function 'f9'" in out
    assert "(showing 10 of 25; re-run vulture for full output)" in out


# ID: dc9ce5a7-a2e8-44f9-968d-ae05664f51f8
def test_verbose_no_footer_when_all_samples_shown(captured: io.StringIO) -> None:
    formatters.print_verbose_findings([_aggregate(issue_count=3, n_samples=3)])
    out = captured.getvalue()
    assert "src/a.py:2: unused function 'f2'" in out
    assert "showing" not in out


# ID: ea88a7b9-cd5d-4873-9f57-012daa405e97
def test_verbose_plain_finding_prints_no_sample_section(
    captured: io.StringIO,
) -> None:
    plain = AuditFinding(
        "starter.no_bare_except", AuditSeverity.BLOCK, "bare except", "src/b.py", 9
    )
    formatters.print_verbose_findings([plain])
    assert "•" not in captured.getvalue()


# ID: 3e88b586-0d40-4708-87ec-121778db9d15
def test_offline_summary_honours_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    shared = Console(file=buf, width=200)
    monkeypatch.setattr(audit_cmd, "console", shared)
    monkeypatch.setattr(formatters, "console", shared)
    monkeypatch.setattr(audit_renderer, "console", shared)
    finding = _aggregate(issue_count=25, n_samples=10).as_dict()
    result = {
        "verdict": "PASS",
        "passed": True,
        "stats": {"total_rules": 1, "executed_rules": 1, "failed_rules": 0},
        "findings": [finding],
        "skipped_rules": [],
        "duration_sec": 0.1,
    }
    audit_cmd._render_text_summary(result, AuditSeverity.INFO, verbose=True)
    out = buf.getvalue()
    assert "Verbose Audit Findings" in out
    assert "(showing 10 of 25; re-run vulture for full output)" in out

    buf.truncate(0)
    buf.seek(0)
    audit_cmd._render_text_summary(result, AuditSeverity.INFO)
    assert "Verbose Audit Findings" not in buf.getvalue()
