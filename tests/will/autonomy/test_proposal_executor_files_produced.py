"""Unit tests for compute_production_set (ADR-101 D2).

The helper unions paths from two sources to derive the action's actual
production boundary:

- ``data['_sandbox_target_paths']``: paths the SandboxLifecycle observed
  modified inside the hermetic worktree (ADR-071 D2.2). Stamped by
  ActionExecutor after a successful propagate_changes.
- ``data['files_produced']``: paths the action explicitly declared as
  produced. The fix.modularity pattern from #297 — actions that write
  new files outside any pre-declared scope list them here.

Both the commit set and the rollback target are derived from this set
per ADR-101 D2/D3. The proposal's permission scope (``scope.files``) is
NOT included — see ADR-101 D1 for why permission and production are
two surfaces, not one.

The helper is purely defensive — non-string and empty entries are
filtered out, missing keys are tolerated — so a malformed action
result can never corrupt the git invocation.
"""

from __future__ import annotations

from will.autonomy.proposal_execution_pipeline import compute_production_set


def test_empty_action_results_returns_empty_list() -> None:
    assert compute_production_set({}) == []


def test_single_action_with_files_produced() -> None:
    results = {
        "fix.modularity:0": {
            "ok": True,
            "data": {"files_produced": ["pkg/a.py", "pkg/b.py", "pkg/__init__.py"]},
        }
    }
    assert compute_production_set(results) == [
        "pkg/__init__.py",
        "pkg/a.py",
        "pkg/b.py",
    ]


def test_single_action_with_sandbox_target_paths() -> None:
    results = {
        "fix.format:0": {
            "ok": True,
            "data": {"_sandbox_target_paths": ["src/x.py", "src/y.py"]},
        }
    }
    assert compute_production_set(results) == ["src/x.py", "src/y.py"]


def test_both_sources_union_and_dedupe() -> None:
    results = {
        "fix.format:0": {
            "ok": True,
            "data": {
                "_sandbox_target_paths": ["src/x.py", "src/y.py"],
                "files_produced": ["src/y.py", "src/z.py"],
            },
        }
    }
    assert compute_production_set(results) == ["src/x.py", "src/y.py", "src/z.py"]


def test_multiple_actions_union_and_dedupe() -> None:
    results = {
        "fix.modularity:0": {
            "ok": True,
            "data": {"files_produced": ["pkg/a.py", "pkg/b.py"]},
        },
        "fix.format:1": {
            "ok": True,
            "data": {"_sandbox_target_paths": ["pkg/b.py", "pkg/c.py"]},
        },
    }
    assert compute_production_set(results) == [
        "pkg/a.py",
        "pkg/b.py",
        "pkg/c.py",
    ]


def test_idempotent_action_produces_empty_set() -> None:
    # ADR-101 D2: action ran sandboxed, sandbox observed no changes, no
    # files_produced declared. compute_production_set returns empty;
    # commit_proposal_changes emits no commit; that is the honest outcome.
    results = {
        "fix.format:0": {
            "ok": True,
            "data": {"formatted": True, "_sandbox_target_paths": []},
        }
    }
    assert compute_production_set(results) == []


def test_action_with_neither_key_is_ignored() -> None:
    results = {
        "fix.format:0": {
            "ok": True,
            "data": {"file": "src/x.py"},  # neither key present
        }
    }
    assert compute_production_set(results) == []


def test_action_with_data_none_is_ignored() -> None:
    results = {"some.action:0": {"ok": False, "data": None}}
    assert compute_production_set(results) == []


def test_action_with_keys_set_to_none_is_ignored() -> None:
    results = {
        "some.action:0": {
            "ok": True,
            "data": {"files_produced": None, "_sandbox_target_paths": None},
        }
    }
    assert compute_production_set(results) == []


def test_non_string_entries_are_filtered() -> None:
    results = {
        "some.action:0": {
            "ok": True,
            "data": {
                "files_produced": ["ok.py", 42, None, {"path": "evil"}, "also_ok.py"]
            },
        }
    }
    assert compute_production_set(results) == ["also_ok.py", "ok.py"]


def test_empty_string_entries_are_filtered() -> None:
    results = {
        "some.action:0": {
            "ok": True,
            "data": {"files_produced": ["", "kept.py", ""]},
        }
    }
    assert compute_production_set(results) == ["kept.py"]


def test_missing_data_key_is_tolerated() -> None:
    # An action result row without a 'data' key at all.
    results = {"some.action:0": {"ok": False, "order": 0}}
    assert compute_production_set(results) == []
