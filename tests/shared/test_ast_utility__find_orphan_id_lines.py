# tests/shared/test_ast_utility__find_orphan_id_lines.py

"""shared.ast_utility.find_orphan_id_lines -- the one definition of "orphaned
# ID: anchor" shared by linkage.no_orphan_ids (Mind, ast_gate) and the cleanup
phase of fix.ids (Body). The fixtures reproduce the 9e9067eb shape: an anchor
separated from its def by a blank line."""

from __future__ import annotations

from shared.ast_utility import find_orphan_id_lines, is_symbol_id_tag


_UID = "a1fb17c6-a4a7-4503-9103-491b28305c2d"
_UID_B = "0b9e1d2c-7a6f-4e5d-8c3b-1a2f3e4d5c6b"


def test_is_symbol_id_tag_matches_only_a_bare_anchor_line() -> None:
    assert is_symbol_id_tag(f"# ID: {_UID}")
    assert is_symbol_id_tag(f"    # ID: {_UID}   ")
    assert not is_symbol_id_tag(f"x = 1  # ID: {_UID}")
    assert not is_symbol_id_tag("# ID:")
    assert not is_symbol_id_tag("# IDENTITY: abc")


def test_attached_anchors_are_not_orphans() -> None:
    source = (
        f"# ID: {_UID}\n"
        "def public():\n"
        "    pass\n"
        "\n"
        "class K:\n"
        f"    # ID: {_UID_B}\n"
        "    async def _private(self):\n"
        "        pass\n"
    )
    assert find_orphan_id_lines(source) == []


def test_anchor_split_from_private_def_by_blank_line_is_an_orphan() -> None:
    # 9e9067eb: the split sat above a private method, which the public-only
    # id_anchor check never inspects.
    source = (
        f"class Worker:\n    # ID: {_UID}\n\n    async def _run(self):\n        pass\n"
    )
    assert find_orphan_id_lines(source) == [(2, f"    # ID: {_UID}")]


def test_file_level_anchor_is_an_orphan() -> None:
    source = f"# ID: {_UID}\n\nimport os\n"
    assert find_orphan_id_lines(source) == [(1, f"# ID: {_UID}")]


def test_anchor_above_a_decorator_is_an_orphan() -> None:
    # CLAUDE.md: decorator -> # ID -> def. Above the decorator, the anchor
    # annotates nothing (find_symbol_id_and_def_line reads the line before
    # the def, after decorators).
    source = f"# ID: {_UID}\n@decorator\ndef f():\n    pass\n"
    assert find_orphan_id_lines(source) == [(1, f"# ID: {_UID}")]


def test_multiple_orphans_reported_in_line_order() -> None:
    source = f"# ID: {_UID}\n\n# ID: {_UID_B}\ndef f():\n    pass\n# ID: {_UID}\n"
    assert find_orphan_id_lines(source) == [
        (1, f"# ID: {_UID}"),
        (6, f"# ID: {_UID}"),
    ]


def test_empty_source() -> None:
    assert find_orphan_id_lines("") == []
