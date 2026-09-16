# tests/shared/test_ast_utility__find_orphan_shadowed_symbols.py

"""shared.ast_utility.find_orphan_shadowed_symbols -- the one definition of
"this public symbol's anchor is the orphan above it; do not regenerate",
consulted by every ID-assigning site (fix.ids, the finding handler,
FileHandler's write-time injection). linkage.no_orphan_ids."""

from __future__ import annotations

from shared.ast_utility import ShadowedSymbol, find_orphan_shadowed_symbols


_UID = "a1fb17c6-a4a7-4503-9103-491b28305c2d"


def test_no_orphans_means_nothing_is_shadowed() -> None:
    assert find_orphan_shadowed_symbols("def f():\n    pass\n") == []
    assert find_orphan_shadowed_symbols(f"# ID: {_UID}\ndef f():\n    pass\n") == []


def test_blank_line_split_shadows_the_public_def_below() -> None:
    src = f"# ID: {_UID}\n\ndef f():\n    pass\n"
    assert find_orphan_shadowed_symbols(src) == [ShadowedSymbol("f", 3, 1)]


def test_orphan_above_single_line_decorator() -> None:
    src = f"# ID: {_UID}\n@deco\ndef f():\n    pass\n"
    assert find_orphan_shadowed_symbols(src) == [ShadowedSymbol("f", 3, 1)]


def test_orphan_above_multiline_decorator() -> None:
    src = f"# ID: {_UID}\n@deco(\n    x=1,\n)\ndef f():\n    pass\n"
    assert find_orphan_shadowed_symbols(src) == [ShadowedSymbol("f", 5, 1)]


def test_orphan_between_decorator_and_def() -> None:
    # anchor is in the right place but followed by a blank line
    src = f"@deco\n# ID: {_UID}\n\ndef f():\n    pass\n"
    assert find_orphan_shadowed_symbols(src) == [ShadowedSymbol("f", 4, 2)]


def test_orphan_separated_by_code_does_not_shadow() -> None:
    src = f"# ID: {_UID}\n\nx = 1\n\ndef f():\n    pass\n"
    assert find_orphan_shadowed_symbols(src) == []


def test_private_symbol_is_never_a_shadow_target() -> None:
    src = f"class K:\n    # ID: {_UID}\n\n    def _g(self):\n        pass\n"
    assert find_orphan_shadowed_symbols(src) == []


def test_file_level_stray_far_from_any_def_does_not_shadow() -> None:
    src = f"# ID: {_UID}\n\nimport os\n\n\ndef f():\n    return os\n"
    assert find_orphan_shadowed_symbols(src) == []


def test_unparseable_source_yields_empty() -> None:
    assert find_orphan_shadowed_symbols(f"# ID: {_UID}\n\ndef (:\n") == []
