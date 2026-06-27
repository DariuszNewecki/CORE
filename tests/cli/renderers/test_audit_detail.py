# tests/cli/renderers/test_audit_detail.py
"""
Tests for cli.renderers.audit_detail — ADR-098 D3 iceberg-tail rendering.

Covers:
- _file_cell: (xN) annotation when issue_count > 1, plain path otherwise
- render_details: uses AuditFinding.check_id / file_path / message (not
  legacy .id / .title / .description which don't exist on AuditFinding)
- Findings without issue_count render unchanged
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from cli.renderers.audit_detail import _file_cell, render_details, truncate
from shared.models import AuditFinding, AuditSeverity
from shared.models.audit_rendering import SeverityGroup


def _finding(
    check_id: str = "quality.type_safety",
    message: str = "2 type error(s) in src/foo.py",
    file_path: str | None = "src/foo.py",
    issue_count: int | None = None,
) -> AuditFinding:
    ctx: dict = {}
    if issue_count is not None:
        ctx["issue_count"] = issue_count
    return AuditFinding(
        check_id=check_id,
        severity=AuditSeverity.INFO,
        message=message,
        file_path=file_path,
        context=ctx,
    )


def _group(*findings: AuditFinding) -> list[SeverityGroup]:
    return [SeverityGroup(severity=AuditSeverity.INFO, findings=tuple(findings))]


def _capture(groups: list[SeverityGroup]) -> str:
    buf = StringIO()
    con = Console(file=buf, no_color=True, highlight=False, markup=False)
    render_details(con, groups)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _file_cell
# ---------------------------------------------------------------------------


def test_file_cell_no_issue_count_returns_path() -> None:
    f = _finding(file_path="src/foo.py")
    assert _file_cell(f) == "src/foo.py"


def test_file_cell_issue_count_one_no_annotation() -> None:
    f = _finding(file_path="src/foo.py", issue_count=1)
    assert _file_cell(f) == "src/foo.py"


def test_file_cell_issue_count_gt1_annotates() -> None:
    f = _finding(file_path="src/foo.py", issue_count=25)
    assert _file_cell(f) == "src/foo.py (x25)"


def test_file_cell_no_file_path_returns_dash() -> None:
    f = _finding(file_path=None)
    assert _file_cell(f) == "-"


def test_file_cell_no_file_path_with_issue_count_no_annotation() -> None:
    f = _finding(file_path=None, issue_count=10)
    assert _file_cell(f) == "-"


# ---------------------------------------------------------------------------
# render_details — field correctness and D3 annotation in output
# ---------------------------------------------------------------------------


def test_render_details_shows_check_id() -> None:
    output = _capture(_group(_finding(check_id="quality.type_safety")))
    assert "quality.type_safety" in output


def test_render_details_shows_message() -> None:
    output = _capture(_group(_finding(message="5 type error(s) in src/bar.py")))
    assert "5 type error(s)" in output


def test_render_details_shows_file_path() -> None:
    output = _capture(_group(_finding(file_path="src/bar.py")))
    assert "src/bar.py" in output


def test_render_details_d3_annotation_in_output() -> None:
    f = _finding(file_path="src/bar.py", issue_count=42)
    output = _capture(_group(f))
    assert "src/bar.py (x42)" in output


def test_render_details_no_annotation_without_issue_count() -> None:
    f = _finding(file_path="src/bar.py")
    output = _capture(_group(f))
    assert "(x" not in output


def test_render_details_empty_group_produces_no_output() -> None:
    groups = [SeverityGroup(severity=AuditSeverity.INFO, findings=())]
    output = _capture(groups)
    assert output.strip() == ""


def test_render_details_multiple_findings() -> None:
    findings = [
        _finding(check_id="quality.type_safety", file_path="src/a.py", issue_count=10),
        _finding(check_id="quality.type_safety", file_path="src/b.py"),
    ]
    output = _capture(_group(*findings))
    assert "src/a.py (x10)" in output
    assert "src/b.py" in output
    assert "src/b.py (x" not in output


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------


def test_truncate_short_string_unchanged() -> None:
    assert truncate("hello", 10) == "hello"


def test_truncate_long_string_adds_ellipsis() -> None:
    result = truncate("hello world", 5)
    assert result == "hello..."
    assert len(result) == 8
