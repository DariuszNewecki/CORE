"""#956: a check that could not run is shown as NOT EVALUATED, not as an
ERROR that "needs human". Display only; verdicts and JSON are unchanged."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from cli.commands.check import formatters
from cli.renderers.audit_overview import render_overview
from shared.models import AuditFinding, AuditSeverity, EvidenceClass
from shared.models.audit_rendering import is_not_evaluated
from shared.utils.audit_grouping import group_findings


def _unavailable() -> AuditFinding:
    return AuditFinding(
        "runtime.worker_max_interval_within_observed",
        AuditSeverity.BLOCK,
        "insufficient evidence to compare configured vs. observed max_interval",
        file_path="System",
        context={"finding_type": "ENFORCEMENT_UNAVAILABLE"},
    )


def _violation() -> AuditFinding:
    return AuditFinding(
        "starter.no_bare_except",
        AuditSeverity.BLOCK,
        "bare except",
        file_path="src/a.py",
        line_number=3,
        evidence_class=EvidenceClass.PROVEN,
    )


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buf = io.StringIO()
    monkeypatch.setattr(formatters, "console", Console(file=buf, width=200))
    return buf


# ID: d86001c3-f055-423e-8be2-ff09ca37317f
def test_is_not_evaluated_recognises_both_types() -> None:
    assert is_not_evaluated(_unavailable())
    failure = AuditFinding(
        "x", AuditSeverity.BLOCK, "m", context={"finding_type": "ENFORCEMENT_FAILURE"}
    )
    assert is_not_evaluated(failure)
    assert not is_not_evaluated(_violation())


@pytest.mark.parametrize(
    "printer", [formatters.print_summary_findings, formatters.print_verbose_findings]
)
# ID: a91abe10-e5b2-4237-97d8-5d738df3b83e
def test_tables_label_not_evaluated_rows(captured: io.StringIO, printer) -> None:
    printer([_unavailable(), _violation()])
    lines = captured.getvalue().splitlines()
    unavailable = next(line for line in lines if "runtime.worker_max" in line)
    violation = next(line for line in lines if "starter.no_bare_except" in line)
    assert "NOT EVALUATED" in unavailable and "unavailable" in unavailable
    assert "BLOCK" not in unavailable and "needs human" not in unavailable
    assert "BLOCK" in violation and "proven" in violation


# ID: decf90d0-f4a5-4254-b4b0-f20441f64f6e
def test_overview_counts_not_evaluated_separately() -> None:
    buf = io.StringIO()
    render_overview(
        Console(file=buf, width=100),
        group_findings([_unavailable(), _violation(), _unavailable()]),
    )
    text = buf.getvalue()
    assert "NOT EVALUATED" in text
    block_row = next(line for line in text.splitlines() if "BLOCK" in line)
    assert " 1 " in block_row  # the one real violation only
    ne_row = next(line for line in text.splitlines() if "NOT EVALUATED" in line)
    assert " 2 " in ne_row
