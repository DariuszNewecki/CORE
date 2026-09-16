# tests/body/self_healing/test_id_tagging_service__orphan_preservation.py

"""fix.ids must never touch an orphaned # ID: anchor (linkage.no_orphan_ids).

Before this change assign_missing_ids opened with a cleanup phase that
stripped every orphan it found -- an undeclared identity loss riding along
with whatever unrelated fix triggered the run (9e9067eb). Now: detect with
the shared helper, leave the bytes alone, report for manual re-attachment,
and refuse to hand a fresh ID to the public symbol the orphan shadows.

The ActionExecutor is stubbed so the exact ``code`` handed to
``file.tag_metadata`` -- the only bytes that could reach disk -- is captured
and inspected. The real write path is exercised by
tests/body/governance/test_intent_guard_823_e2e_fixids.py (integration).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

import body.self_healing.id_tagging_service as svc
from shared.ast_utility import find_orphan_id_lines


_ORPHAN = "a1fb17c6-a4a7-4503-9103-491b28305c2d"
_ATTACHED = "5f1c2a6e-3f1c-4b0a-9c8d-2e7f1a3b4c5d"
_UUID_LINE = re.compile(r"^\s*# ID: [0-9a-f-]{36}$", re.MULTILINE)

# One file, four situations:
#   - a file-level stray anchor (orphan, shadows nothing)
#   - a public symbol whose anchor was split off by a blank line (orphan
#     shadows `split_public`; fix.ids must NOT re-tag it)
#   - a public symbol simply missing an ID (unrelated; fix.ids tags it)
#   - a private method under a split anchor (orphan; private, never tagged)
_SOURCE = (
    f"# ID: {_ORPHAN}\n"
    "\n"
    "import os\n"
    "\n"
    "\n"
    f"# ID: {_ATTACHED}\n"
    "\n"
    "def split_public():\n"
    "    return os\n"
    "\n"
    "\n"
    "def untagged_public():\n"
    "    pass\n"
    "\n"
    "\n"
    "# ID: 0b9e1d2c-7a6f-4e5d-8c3b-1a2f3e4d5c6b\n"
    "class K:\n"
    f"    # ID: {_ORPHAN}\n"
    "\n"
    "    def _private(self):\n"
    "        pass\n"
)


class _CapturingExecutor:
    """Stands in for ActionExecutor; records every file.tag_metadata call."""

    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, context: Any) -> None:
        pass

    async def execute(self, action_id: str, **kwargs: Any) -> Any:
        _CapturingExecutor.calls.append({"action_id": action_id, **kwargs})
        return SimpleNamespace(ok=True, data={})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "probe.py").write_text(_SOURCE, encoding="utf-8")
    _CapturingExecutor.calls = []
    monkeypatch.setattr(svc, "ActionExecutor", _CapturingExecutor)
    return tmp_path


def _context(repo: Path) -> Any:
    return SimpleNamespace(git_service=SimpleNamespace(repo_path=repo))


async def test_orphan_anchor_bytes_survive_a_fix_ids_run(repo: Path) -> None:
    report = await svc.assign_missing_ids(_context(repo), write=True)

    # exactly one write, and it only inserted -- never deleted -- a comment
    assert [c["action_id"] for c in _CapturingExecutor.calls] == ["file.tag_metadata"]
    call = _CapturingExecutor.calls[0]
    assert call["allowed_operations"] == ["comment.insert"]
    written: str = call["code"]

    # every original line is still present, in order, byte for byte
    original_lines = _SOURCE.splitlines()
    written_lines = written.splitlines()
    it = iter(written_lines)
    assert all(any(line == w for w in it) for line in original_lines), (
        "fix.ids dropped or altered an original line"
    )
    # both orphan anchors are still there, untouched
    assert written.count(f"# ID: {_ORPHAN}") == 2
    assert f"# ID: {_ATTACHED}\n\ndef split_public" in written

    # the only addition is one fresh anchor on the unrelated symbol
    assert len(written_lines) == len(original_lines) + 1
    new_anchor = [ln for ln in written_lines if ln not in original_lines]
    assert len(new_anchor) == 1 and _UUID_LINE.match(new_anchor[0])
    assert f"{new_anchor[0]}\ndef untagged_public" in written
    assert report.ids_assigned == 1


async def test_shadowed_symbol_is_not_regenerated_and_is_reported(repo: Path) -> None:
    report = await svc.assign_missing_ids(_context(repo), write=False)

    # detector and fixer agree on the orphan set
    assert sorted(o.line_number for o in report.orphan_anchors) == sorted(
        n for n, _ in find_orphan_id_lines(_SOURCE)
    )
    by_line = {o.line_number: o for o in report.orphan_anchors}
    assert by_line[1].symbol is None  # file-level stray, shadows nothing
    assert by_line[6].symbol == "split_public"  # its own identity, split off
    assert by_line[18].symbol is None  # private method: never a fix target
    assert [o.symbol for o in report.reattachment_required] == ["split_public"]
    assert all(o.file_path == "src/probe.py" for o in report.orphan_anchors)

    # split_public was NOT queued for a fresh ID; untagged_public was
    written: str = _CapturingExecutor.calls[0]["code"]
    assert not re.search(r"# ID: [0-9a-f-]{36}\ndef split_public", written)
    assert re.search(r"# ID: [0-9a-f-]{36}\ndef untagged_public", written)


async def test_orphan_above_multiline_decorator_shadows_the_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = f"# ID: {_ORPHAN}\n@deco(\n    x=1,\n)\ndef decorated():\n    pass\n"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "d.py").write_text(src, encoding="utf-8")
    _CapturingExecutor.calls = []
    monkeypatch.setattr(svc, "ActionExecutor", _CapturingExecutor)

    report = await svc.assign_missing_ids(_context(tmp_path), write=False)

    assert [o.symbol for o in report.reattachment_required] == ["decorated"]
    assert _CapturingExecutor.calls == []  # nothing to write at all


async def test_fix_ids_action_result_reports_orphans(repo: Path) -> None:
    # fix_ids_internal is @atomic_action-guarded; tests call the underlying
    # function via ``.__wrapped__`` (precedent: tests/body/atomic/test_assisted_actions.py).
    result = await svc.fix_ids_internal.__wrapped__(_context(repo), write=False)

    assert result.ok
    assert result.data["ids_assigned"] == 1
    assert result.data["reattachment_required"] == 1
    orphans = result.data["orphan_anchors"]
    assert {o["line_number"] for o in orphans} == {1, 6, 18}
    assert [o["shadowed_symbol"] for o in orphans if o["line_number"] == 6] == [
        "split_public"
    ]
