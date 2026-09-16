# tests/body/self_healing/test_id_tagging_service__strip_orphan_ids.py

"""fix.ids' cleanup phase strips exactly the set linkage.no_orphan_ids flags --
both are built on shared.ast_utility.find_orphan_id_lines, and this pins the
equivalence so the gate and the fixer cannot drift apart."""

from __future__ import annotations

from body.self_healing.id_tagging_service import _strip_orphan_ids
from shared.ast_utility import find_orphan_id_lines


_UID = "a1fb17c6-a4a7-4503-9103-491b28305c2d"
_UID_B = "0b9e1d2c-7a6f-4e5d-8c3b-1a2f3e4d5c6b"

_SOURCE = (
    f"# ID: {_UID_B}\n"
    "\n"
    f"# ID: {_UID}\n"
    "def f():\n"
    "    pass\n"
    "\n"
    "class K:\n"
    f"    # ID: {_UID_B}\n"
    "\n"
    "    def _g(self):\n"
    "        pass\n"
)


def test_clean_source_is_returned_unchanged() -> None:
    source = f"# ID: {_UID}\ndef f():\n    pass\n"
    assert _strip_orphan_ids(source) == (source, 0)


def test_strips_exactly_the_lines_the_detector_reports() -> None:
    orphans = find_orphan_id_lines(_SOURCE)
    cleaned, removed = _strip_orphan_ids(_SOURCE)

    assert removed == len(orphans) == 2
    expected = "".join(
        line
        for i, line in enumerate(_SOURCE.splitlines(keepends=True), start=1)
        if i not in {n for n, _ in orphans}
    )
    assert cleaned == expected
    # the attached anchor on f() survives; the two orphans are gone
    assert f"# ID: {_UID}\ndef f():" in cleaned
    assert cleaned.count("# ID:") == 1


def test_strip_is_idempotent() -> None:
    cleaned, _ = _strip_orphan_ids(_SOURCE)
    assert _strip_orphan_ids(cleaned) == (cleaned, 0)
