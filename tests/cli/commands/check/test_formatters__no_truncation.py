"""#1187: at 80 columns the findings tables cut the rule id to
`starter.no_bare` and the location to `src/myproject/r` (no `:8`). The
rule id and file:line are never cut at any width; the message wraps, and a
table that does not fit prints one finding per block."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from cli.commands.check import formatters
from shared.models import AuditFinding, AuditSeverity, EvidenceClass


_ID = "starter.no_bare_except"
_LOCATION = "src/myproject/risky.py:8"


def _findings() -> list[AuditFinding]:
    return [
        AuditFinding(
            _ID,
            AuditSeverity.BLOCK,
            "Line 8: bare 'except:' catches SystemExit and KeyboardInterrupt",
            file_path="src/myproject/risky.py",
            line_number=8,
            evidence_class=EvidenceClass.PROVEN,
        ),
        AuditFinding(
            "starter.docstrings",
            AuditSeverity.HIGH,
            "Missing docstring",
            file_path="src/myproject/a_rather_long_module_name_for_testing.py",
            line_number=123,
        ),
    ]


def _render(monkeypatch: pytest.MonkeyPatch, width: int, printer) -> str:
    buf = io.StringIO()
    monkeypatch.setattr(formatters, "console", Console(file=buf, width=width))
    printer(_findings())
    return buf.getvalue()


@pytest.mark.parametrize("width", [60, 80, 100, 120])
# ID: c0792465-f44d-466f-bb31-2c90d27f0e9b
def test_verbose_never_cuts_rule_id_or_location(
    monkeypatch: pytest.MonkeyPatch, width: int
) -> None:
    out = _render(monkeypatch, width, formatters.print_verbose_findings)
    assert _ID in out
    assert _LOCATION in out
    assert "src/myproject/a_rather_long_module_name_for_testing.py:123" in out
    assert "starter.docstrings" in out
    assert all(len(line) <= width for line in out.splitlines() if "│" in line)


@pytest.mark.parametrize("width", [60, 80, 100, 120])
# ID: 50775fcd-0357-4f64-8734-2945c2c7a3a7
def test_summary_never_cuts_rule_id(
    monkeypatch: pytest.MonkeyPatch, width: int
) -> None:
    out = _render(monkeypatch, width, formatters.print_summary_findings)
    assert _ID in out
    assert "starter.docstrings" in out


# ID: 76288079-b174-4fd5-9734-70ce9152d3d7
def test_wide_console_keeps_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _render(monkeypatch, 160, formatters.print_verbose_findings)
    row = next(line for line in out.splitlines() if _ID in line)
    assert "│" in row and _LOCATION in row
