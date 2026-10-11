# tests/shared/test_config_roots_follow_repo_path.py
"""Roots follow an explicit REPO_PATH (ADR-132 D10 · D2, C1).

Each root used to discover its own default from the working directory, so
REPO_PATH alone left MIND and the rest pointing elsewhere; under a release
runtime with an empty working directory MIND fell back to the machinery
floor. An explicitly set root still wins (law kept outside the code clone).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import Settings


# ID: e09d1bd4-b550-44c9-b10e-32302699956f
def test_repo_path_from_environment_moves_every_unset_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPO_PATH", str(tmp_path))
    s = Settings()
    assert s.REPO_PATH == tmp_path
    assert s.MIND == tmp_path / ".intent"
    assert s.SPECS == tmp_path / ".specs"
    assert s.BODY == tmp_path / "src"
    assert s.KEY_STORAGE_DIR == tmp_path / ".intent" / "keys"
    assert Path(s.CORE_ACTION_LOG_PATH) == tmp_path / "var" / "logs" / "actions.jsonl"


# ID: 16128d1e-5063-4ffa-a258-d3b23d8e4bd3
def test_explicit_law_roots_outside_the_clone_win(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, law = tmp_path / "repo", tmp_path / "law"
    monkeypatch.setenv("REPO_PATH", str(repo))
    monkeypatch.setenv("MIND", str(law / ".intent"))
    monkeypatch.setenv("SPECS", str(law / ".specs"))
    s = Settings()
    assert s.MIND == law / ".intent"
    assert s.SPECS == law / ".specs"
    assert s.KEY_STORAGE_DIR == law / ".intent" / "keys"
    assert s.BODY == repo / "src"
    assert s.paths.intent_root == law / ".intent"


# ID: 367e11f5-27ed-42d6-97ef-0bb3a7e77ec9
def test_constructor_repo_path_also_moves_roots(tmp_path: Path) -> None:
    s = Settings(REPO_PATH=tmp_path)
    assert s.MIND == tmp_path / ".intent"


# ID: 36ed88b8-2340-40b2-b47e-2243aa2d2afa
def test_without_repo_path_discovery_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REPO_PATH", raising=False)
    s = Settings()
    assert "REPO_PATH" not in s.model_fields_set
    assert s.MIND == s.REPO_PATH / ".intent"
