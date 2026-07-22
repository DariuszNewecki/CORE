# tests/mind/logic/engines/ast_gate/test_duplicate_ids_check.py

"""Tests for the stateless corpus duplicate symbol-ID check (#820 Group C).

Covers ast_gate's replacement for the retired knowledge_gate mechanism:
detect ``# ID: <uuid>`` anchors that collide across src/, reading files
directly (no knowledge graph).
"""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.ast_gate.checks.duplicate_ids_check import check_duplicate_ids
from shared.models import AuditSeverity


class _StubContext:
    """Minimal AuditorContext stand-in: only get_files is exercised."""

    def __init__(self, files: list[Path]) -> None:
        self._files = files

    def get_files(self, include: list[str], exclude: list[str]) -> list[Path]:
        return self._files


_UID = "ad64d745-9b17-4709-bec7-d84d8d2c1145"
_UID_B = "e2e5faff-20e7-48a0-ad44-5ef2720d2104"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_duplicate_id_across_two_files_is_blocked(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.py", f"# ID: {_UID}\ndef alpha():\n    pass\n")
    b = _write(tmp_path, "b.py", f"# ID: {_UID}\ndef beta():\n    pass\n")

    findings = check_duplicate_ids(_StubContext([a, b]), {})

    assert len(findings) == 1
    f = findings[0]
    assert f.severity is AuditSeverity.BLOCK
    assert f.check_id == "linkage.duplicate_ids"
    assert _UID in f.message
    assert len(f.context["duplicates"]) == 2


def test_unique_ids_pass(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.py", f"# ID: {_UID}\ndef alpha():\n    pass\n")
    b = _write(tmp_path, "b.py", f"# ID: {_UID_B}\ndef beta():\n    pass\n")

    findings = check_duplicate_ids(_StubContext([a, b]), {})

    assert findings == []


def test_duplicate_within_a_single_file_is_blocked(tmp_path: Path) -> None:
    a = _write(
        tmp_path,
        "a.py",
        f"# ID: {_UID}\ndef alpha():\n    pass\n\n# ID: {_UID}\ndef gamma():\n    pass\n",
    )

    findings = check_duplicate_ids(_StubContext([a]), {})

    assert len(findings) == 1
    assert len(findings[0].context["duplicates"]) == 2


def test_placeholder_anchors_are_ignored(tmp_path: Path) -> None:
    # Malformed/placeholder anchors are not real UUID collisions — the
    # assign_ids/hook layer owns those, not duplicate detection.
    a = _write(tmp_path, "a.py", "# ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\ndef a():\n    pass\n")
    b = _write(tmp_path, "b.py", "# ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\ndef b():\n    pass\n")

    findings = check_duplicate_ids(_StubContext([a, b]), {})

    assert findings == []
