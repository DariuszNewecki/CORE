"""ADR-098 D1/D2/D3 — aggregate quality gates emit per-affected-file findings.

Before ADR-098, ``QualityGateCheck`` discarded every line of tool output
after the first and returned one collapsed string — 779 mypy errors rendered
as a single INFO finding (issue #602/#603, the iceberg). This suite locks in:

- D1: mypy output yields one ``StructuredViolation`` per affected file.
- D2: each violation carries ``tool`` / ``issue_count`` / ``sample_issues``
  (capped at 10) / ``first_issue_line`` in its context.
- Engine wrapping: ``verify_context`` turns each StructuredViolation into one
  ``AuditFinding`` preserving ``file_path`` and ``context``.
- D3: the overview renderer surfaces the underlying-issue rollup, and skips
  it entirely for ordinary (non-aggregate) findings.

Severity is intentionally not asserted here: ``rule_executor`` derives it
from the rule's declared enforcement (ADR-098 D4) after the engine returns.
"""

from __future__ import annotations

import asyncio
import io
from unittest.mock import AsyncMock, MagicMock, patch

from rich.console import Console

from cli.renderers.audit_overview import render_overview
from mind.logic.engines.workflow_gate.base_check import StructuredViolation
from mind.logic.engines.workflow_gate.checks.quality import QualityGateCheck
from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine
from shared.models import AuditFinding, AuditSeverity
from shared.utils.audit_grouping import group_findings


_MYPY_OUTPUT = (
    "src/a.py:10: error: Item None has no attribute repo_path  [union-attr]\n"
    "src/a.py:12: error: bar  [attr-defined]\n"
    "src/b.py:3: error: baz  [arg-type]\n"
    "Found 3 errors in 2 files (checked 5 source files)"
)


def _path_resolver() -> MagicMock:
    pr = MagicMock()
    pr.repo_root = "/repo"
    return pr


def _run_verify(check_type: str, output: str) -> list:
    """Run QualityGateCheck.verify with a mocked nonzero-exit subprocess."""
    check = QualityGateCheck(_path_resolver(), check_type, ["tool"])

    async def fake_exec(*args, **kwargs):
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(output.encode(), b""))
        proc.returncode = 1
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        return list(asyncio.run(check.verify(None, {})))


def test_mypy_emits_one_violation_per_affected_file() -> None:
    """D1: two affected files → two StructuredViolations, not one collapsed string."""
    result = _run_verify("mypy_check", _MYPY_OUTPUT)

    assert len(result) == 2
    assert all(isinstance(v, StructuredViolation) for v in result)
    by_path = {v.file_path: v for v in result}
    assert set(by_path) == {"src/a.py", "src/b.py"}


def test_mypy_violation_carries_structured_context() -> None:
    """D2: per-file context has tool, issue_count, sample_issues, first_issue_line."""
    result = _run_verify("mypy_check", _MYPY_OUTPUT)
    a = next(v for v in result if v.file_path == "src/a.py")

    assert a.context["tool"] == "mypy"
    assert a.context["issue_count"] == 2
    assert a.context["first_issue_line"] == 10
    assert len(a.context["sample_issues"]) == 2
    assert "src/a.py:10:" in a.context["sample_issues"][0]


def test_total_underlying_issue_count_equals_source() -> None:
    """The sum of per-file issue_count equals the real error total (honesty)."""
    result = _run_verify("mypy_check", _MYPY_OUTPUT)
    assert sum(v.context["issue_count"] for v in result) == 3


def test_sample_issues_capped_at_ten_but_count_is_full() -> None:
    """D2: sample_issues bounded to 10; issue_count reflects the true total."""
    lines = [f"src/big.py:{i}: error: e{i}  [misc]" for i in range(1, 26)]
    result = _run_verify("mypy_check", "\n".join(lines))

    assert len(result) == 1
    assert result[0].context["issue_count"] == 25
    assert len(result[0].context["sample_issues"]) == 10


def test_security_gate_degrades_to_single_honest_finding() -> None:
    """pip-audit (not keyed per-file yet) → one finding on pyproject.toml."""
    result = _run_verify("security_check", "starlette 0.1 GHSA-x\npip 1.0 PYSEC-y")

    assert len(result) == 1
    assert result[0].file_path == "pyproject.toml"
    assert result[0].context["tool"] == "pip_audit"
    assert result[0].context["issue_count"] == 2


def test_mypy_crash_without_parseable_lines_falls_back() -> None:
    """Nonzero exit with no file:line errors still surfaces one finding."""
    result = _run_verify("mypy_check", "mypy: internal error: boom")

    assert len(result) == 1
    assert result[0].context["issue_count"] >= 1


def test_engine_wraps_structured_violations_preserving_context() -> None:
    """verify_context builds one AuditFinding per StructuredViolation, keeping context."""
    engine = WorkflowGateEngine(_path_resolver())

    stub = MagicMock()
    stub.verify = AsyncMock(
        return_value=[
            StructuredViolation(
                file_path="src/a.py",
                message="2 type error(s) in src/a.py",
                context={"tool": "mypy", "issue_count": 2},
            )
        ]
    )
    engine._checks["mypy_check"] = stub

    findings = asyncio.run(
        engine.verify_context(MagicMock(), {"check_type": "mypy_check"})
    )

    assert len(findings) == 1
    assert findings[0].file_path == "src/a.py"
    assert findings[0].context["issue_count"] == 2


def test_overview_rollup_reports_underlying_issue_total() -> None:
    """D3: rollup shows findings-vs-underlying for aggregate-gate findings."""
    findings = [
        AuditFinding(
            "quality.type_safety",
            AuditSeverity.INFO,
            "25 type error(s) in src/a.py",
            file_path="src/a.py",
            context={"tool": "mypy", "issue_count": 25},
        ),
        AuditFinding(
            "quality.type_safety",
            AuditSeverity.INFO,
            "1 type error(s) in src/b.py",
            file_path="src/b.py",
            context={"tool": "mypy", "issue_count": 1},
        ),
    ]
    buf = io.StringIO()
    render_overview(Console(file=buf, width=100), group_findings(findings))
    text = buf.getvalue()

    assert "Aggregate Quality Gates" in text
    assert "underlying" in text.lower()
    assert "26" in text  # 25 + 1 underlying issues


def test_overview_rollup_absent_for_ordinary_findings() -> None:
    """The rollup is opt-in: findings without issue_count never trigger it."""
    findings = [
        AuditFinding(
            "arch.some_rule", AuditSeverity.HIGH, "ordinary", file_path="src/c.py"
        )
    ]
    buf = io.StringIO()
    render_overview(Console(file=buf, width=100), group_findings(findings))

    assert "Aggregate Quality Gates" not in buf.getvalue()
