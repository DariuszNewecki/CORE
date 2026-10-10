# tests/shared/infrastructure/intent/test_governed_text.py
"""governed_text: the paths a code proposal may not touch (ADR-168 A5 / R5)."""

from __future__ import annotations

from unittest.mock import patch

from shared.infrastructure.intent.governed_text import (
    governed_paths_touched,
    load_governed_text_paths,
)


_GOVERNED = (
    ".intent/",
    ".specs/",
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/hooks/",
)


# ID: 5954a06f-8be4-490f-a120-bbe45e8eb18d
def test_directory_entries_cover_everything_beneath_them() -> None:
    hits = governed_paths_touched(
        [".intent/rules/a.json", "./.specs/papers/p.md", ".claude/hooks/x.sh"],
        _GOVERNED,
    )
    assert hits == [
        ".intent/rules/a.json",
        "./.specs/papers/p.md",
        ".claude/hooks/x.sh",
    ]


# ID: ca253390-b147-44b8-b97a-483334d463dd
def test_file_entries_match_only_that_file() -> None:
    assert governed_paths_touched(["CLAUDE.md"], _GOVERNED) == ["CLAUDE.md"]
    assert (
        governed_paths_touched(
            ["docs/CLAUDE.md", ".claude/settings.local.json", "src/intent/x.py"],
            _GOVERNED,
        )
        == []
    )


# ID: d2550542-bca0-4465-aff0-798b7b527f78
def test_the_law_of_record_declares_specs_and_claude_md() -> None:
    paths = load_governed_text_paths()
    assert ".specs/" in paths
    assert "CLAUDE.md" in paths


# ID: 949568d1-9344-4f23-ac26-aea2029ed4a0
def test_unreadable_law_falls_back_to_intent_only() -> None:
    with patch(
        "shared.infrastructure.intent.governed_text.get_intent_repository",
        side_effect=RuntimeError("no law"),
    ):
        assert load_governed_text_paths() == (".intent/",)
