# tests/shared/infrastructure/intent/test_law_roots.py
"""Where a repository's law lives (ADR-132 D10 · D2).

Explicit MIND/SPECS + a root inside CORE's configured repository (the clone
or one of its sandboxes) -> the configured law beside the clone. Anything
else -> ``<root>/.intent`` / ``<root>/.specs``, exactly as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import Settings
from shared.infrastructure.intent.law_roots import intent_root_for, specs_root_for
from shared.path_resolver import PathResolver


@pytest.fixture
def d2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Settings as the D2 services see them: code clone + law beside it."""
    repo, law = tmp_path / "repo", tmp_path / "law"
    repo.mkdir()
    s = Settings(REPO_PATH=repo, MIND=law / ".intent", SPECS=law / ".specs")
    monkeypatch.setattr("shared.config.settings", s)
    return repo, law


# ID: ec4fec84-0614-4307-b430-cea676e9cb5f
def test_clone_reads_the_law_beside_it(d2: tuple[Path, Path]) -> None:
    repo, law = d2
    assert intent_root_for(repo) == law / ".intent"
    assert specs_root_for(repo) == law / ".specs"


# ID: 26ecdab9-a328-4e1f-99a8-1d430d13a050
def test_sandbox_inside_the_clone_reads_the_same_law(d2: tuple[Path, Path]) -> None:
    repo, law = d2
    sandbox = repo / "var" / "tmp" / "core-action-sandbox-x"
    assert intent_root_for(sandbox) == law / ".intent"


# ID: bf9a5fa4-359d-4c55-947d-ec6c74ecee3b
def test_external_target_keeps_its_own_law(
    d2: tuple[Path, Path], tmp_path: Path
) -> None:
    target = tmp_path / "someone-elses-repo"
    assert intent_root_for(target) == target / ".intent"
    assert specs_root_for(target) == target / ".specs"


# ID: 28f6d915-d4bd-41cb-83d5-cec58a31f3ca
def test_without_explicit_law_roots_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = Settings(REPO_PATH=tmp_path)  # MIND derived, not set explicitly
    monkeypatch.setattr("shared.config.settings", s)
    assert intent_root_for(tmp_path) == tmp_path / ".intent"
    assert specs_root_for(tmp_path) == tmp_path / ".specs"


# ID: 027ca055-0e6a-44c6-bb65-b4bfab31cd3e
def test_path_resolver_default_follows_the_law_root(d2: tuple[Path, Path]) -> None:
    repo, law = d2
    assert PathResolver(repo).intent_root == law / ".intent"
    assert PathResolver(repo).workers_dir == law / ".intent" / "workers"
    explicit = PathResolver.from_repo(repo, intent_root=Path("/elsewhere"))
    assert explicit.intent_root == Path("/elsewhere")
