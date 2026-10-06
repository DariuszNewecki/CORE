"""ADR-169 D2: the law evaluated vs the law of record, against a real git repo.

MATCH exactly when the live .intent/ is the committed .intent/; DRIFT names the
differing paths (modified, untracked, deleted); ignored files are outside both;
outside a git work tree the relationship is UNKNOWN, never MATCH.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.intent.law_state import (
    LAW_DRIFT_CHECK_ID,
    LAW_DRIFT_FINDING_TYPE,
    LawState,
    law_digest,
    law_drift_findings,
    observe_law_state,
)
from shared.models.audit_models import AuditSeverity


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose committed .intent/ has two files and an ignored key."""
    _git(tmp_path, "init", "-q")
    (tmp_path / ".intent/rules").mkdir(parents=True)
    (tmp_path / ".intent/rules/a.json").write_text('{"rules": []}\n')
    (tmp_path / ".intent/policy.yaml").write_text("x: 1\n")
    (tmp_path / ".gitignore").write_text(".intent/keys/\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "law")
    return tmp_path


def test_committed_law_matches(repo: Path) -> None:
    state = observe_law_state(repo / ".intent")
    assert state.relationship == "MATCH"
    assert state.record_digest == state.evaluated_digest
    assert state.head_sha and len(state.head_sha) == 40
    assert state.drift_paths == []
    assert law_drift_findings(state) == []


def test_modified_law_drifts_and_names_the_path(repo: Path) -> None:
    (repo / ".intent/policy.yaml").write_text("x: 2\n")
    state = observe_law_state(repo / ".intent")
    assert state.relationship == "DRIFT"
    assert state.record_digest != state.evaluated_digest
    assert state.drift_paths == [".intent/policy.yaml"]


def test_untracked_and_deleted_law_files_drift(repo: Path) -> None:
    (repo / ".intent/rules/new.json").write_text("{}\n")
    (repo / ".intent/rules/a.json").unlink()
    state = observe_law_state(repo / ".intent")
    assert state.relationship == "DRIFT"
    assert state.drift_paths == [".intent/rules/a.json", ".intent/rules/new.json"]


def test_staged_but_uncommitted_law_still_drifts(repo: Path) -> None:
    """The law of record is HEAD, not the index."""
    (repo / ".intent/policy.yaml").write_text("x: 3\n")
    _git(repo, "add", ".intent/policy.yaml")
    assert observe_law_state(repo / ".intent").relationship == "DRIFT"


def test_ignored_files_and_changes_outside_intent_do_not_drift(repo: Path) -> None:
    (repo / ".intent/keys").mkdir()
    (repo / ".intent/keys/private.key").write_text("secret\n")
    (repo / "src/app.py").write_text("x = 2\n")
    assert observe_law_state(repo / ".intent").relationship == "MATCH"


def test_committing_the_edit_restores_match(repo: Path) -> None:
    (repo / ".intent/policy.yaml").write_text("x: 4\n")
    _git(repo, "commit", "-q", "-am", "amend law")
    assert observe_law_state(repo / ".intent").relationship == "MATCH"


def test_repository_without_a_commit_is_unknown_and_logs_no_git_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """#958: `git init` without a commit is a known state. The relationship is
    UNKNOWN (never MATCH), the reason says what to do, and no git failure is
    logged at WARNING or above."""
    _git(tmp_path, "init", "-q")
    (tmp_path / ".intent").mkdir()
    (tmp_path / ".intent/policy.yaml").write_text("x: 1\n")
    with caplog.at_level("DEBUG"):
        state = observe_law_state(tmp_path / ".intent")
    assert state.relationship == "UNKNOWN"
    assert state.reason and "no commit yet" in state.reason
    assert "commit .intent/" in state.reason
    assert not [r for r in caplog.records if r.levelno >= 30]
    (finding,) = law_drift_findings(state)
    assert "no commit yet" in finding.message


def test_outside_a_git_work_tree_is_unknown_never_match(tmp_path: Path) -> None:
    (tmp_path / ".intent").mkdir()
    state = observe_law_state(tmp_path / ".intent")
    assert state.relationship == "UNKNOWN"
    assert state.reason
    [finding] = law_drift_findings(state)
    assert finding.context["relationship"] == "UNKNOWN"


def test_drift_findings_degrade_and_never_fail(repo: Path) -> None:
    (repo / ".intent/policy.yaml").write_text("x: 5\n")
    [finding] = law_drift_findings(observe_law_state(repo / ".intent"))
    assert finding.check_id == LAW_DRIFT_CHECK_ID
    assert finding.file_path == ".intent/policy.yaml"
    assert finding.severity == AuditSeverity.MEDIUM
    assert finding.context["finding_type"] == LAW_DRIFT_FINDING_TYPE
    assert (
        finding.context["law_record_digest"] != finding.context["law_evaluated_digest"]
    )


def test_digest_is_order_independent_and_content_sensitive() -> None:
    assert law_digest({"a": "1", "b": "2"}) == law_digest({"b": "2", "a": "1"})
    assert law_digest({"a": "1"}) != law_digest({"a": "2"})


def test_to_dict_round_trips() -> None:
    state = LawState(relationship="DRIFT", head_sha="h", drift_paths=["p"])
    assert LawState(**state.to_dict()) == state
