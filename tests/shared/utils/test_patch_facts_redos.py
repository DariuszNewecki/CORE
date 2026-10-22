# tests/shared/utils/test_patch_facts_redos.py
"""The diff --git header parse is linear (CodeQL py/polynomial-redos)."""

from __future__ import annotations

import time

from shared.utils.patch_facts import _diff_git_target, read_patch


# ID: 1f7c3e92-5a48-4d6b-b0e1-8c2d9a7f4e53
def test_header_split_matches_git() -> None:
    assert _diff_git_target("diff --git a/x.py b/x.py") == "x.py"
    assert _diff_git_target("diff --git a/a b/c b/d") == "c b/d"
    assert _diff_git_target("diff --git a/x b/") is None
    assert _diff_git_target("+++ b/x.py") is None


# ID: 8b2e6f14-3c97-4a5d-9e0b-7d1a5c3f2b68
def test_crafted_header_is_read_quickly() -> None:
    line = "diff --git a/a b/" + "a b/a" * 50_000
    start = time.monotonic()
    read_patch(line)
    assert time.monotonic() - start < 1.0
