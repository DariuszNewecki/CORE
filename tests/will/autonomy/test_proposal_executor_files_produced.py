"""Unit tests for _files_produced_by (issue #297).

The helper collects file paths reported by actions via
``ActionResult.data['files_produced']`` so the commit step can stage
new files alongside ``proposal.scope.files``. Without this, actions
like ``fix.modularity`` produce package splits whose new files never
reach git, leaving the auto-commit as deletion-only.

The helper is purely defensive — non-string and empty entries are
filtered out, missing keys are tolerated — so a malformed action
result can never corrupt the git-add invocation.
"""

from __future__ import annotations

from will.autonomy.proposal_execution_pipeline import _files_produced_by


def test_empty_action_results_returns_empty_set() -> None:
    assert _files_produced_by({}) == set()


def test_single_action_with_files_produced() -> None:
    results = {
        "fix.modularity:0": {
            "ok": True,
            "data": {"files_produced": ["pkg/a.py", "pkg/b.py", "pkg/__init__.py"]},
        }
    }
    assert _files_produced_by(results) == {"pkg/a.py", "pkg/b.py", "pkg/__init__.py"}


def test_multiple_actions_union_and_dedupe() -> None:
    results = {
        "fix.modularity:0": {
            "ok": True,
            "data": {"files_produced": ["pkg/a.py", "pkg/b.py"]},
        },
        "fix.modularity:1": {
            "ok": True,
            "data": {"files_produced": ["pkg/b.py", "pkg/c.py"]},
        },
    }
    assert _files_produced_by(results) == {"pkg/a.py", "pkg/b.py", "pkg/c.py"}


def test_action_without_files_produced_key_is_ignored() -> None:
    results = {
        "fix.format:0": {
            "ok": True,
            "data": {"file": "src/x.py"},  # no files_produced key
        }
    }
    assert _files_produced_by(results) == set()


def test_action_with_data_none_is_ignored() -> None:
    results = {"some.action:0": {"ok": False, "data": None}}
    assert _files_produced_by(results) == set()


def test_action_with_files_produced_none_is_ignored() -> None:
    results = {
        "some.action:0": {"ok": True, "data": {"files_produced": None}}
    }
    assert _files_produced_by(results) == set()


def test_non_string_entries_are_filtered() -> None:
    results = {
        "some.action:0": {
            "ok": True,
            "data": {"files_produced": ["ok.py", 42, None, {"path": "evil"}, "also_ok.py"]},
        }
    }
    assert _files_produced_by(results) == {"ok.py", "also_ok.py"}


def test_empty_string_entries_are_filtered() -> None:
    results = {
        "some.action:0": {
            "ok": True,
            "data": {"files_produced": ["", "kept.py", ""]},
        }
    }
    assert _files_produced_by(results) == {"kept.py"}


def test_missing_data_key_is_tolerated() -> None:
    # An action result row without a 'data' key at all.
    results = {"some.action:0": {"ok": False, "order": 0}}
    assert _files_produced_by(results) == set()
