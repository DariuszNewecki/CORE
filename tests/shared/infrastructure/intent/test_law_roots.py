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
from shared.infrastructure.intent.law_roots import (
    configured_repo_root,
    intent_root_for,
    law_glob,
    law_path,
    law_relpath,
    specs_root_for,
)
from shared.path_resolver import PathResolver


@pytest.fixture
def d2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Settings as the D2 services see them: code clone + law beside it."""
    repo, law = tmp_path / "repo", tmp_path / "law"
    repo.mkdir()
    s = Settings(REPO_PATH=repo, MIND=law / ".intent", SPECS=law / ".specs")
    monkeypatch.setattr("shared.config.settings", s)
    run = tmp_path / "run"  # the services' working directory: no law up the chain
    run.mkdir()
    monkeypatch.chdir(run)
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


# ID: 1298ecb4-c911-4a51-b2d1-c97f3b2f5ed4
def test_dev_worktree_keeps_its_own_law_under_an_explicit_repo_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A development checkout whose .env sets REPO_PATH: config fills MIND in
    from it (and so marks it set). That is not law beside the clone, so a
    worktree inside the checkout -- a sandbox, or the law-proposal scratch
    worktree -- must still read its own law."""
    s = Settings(REPO_PATH=tmp_path)
    assert "MIND" in s.model_fields_set  # the trap: filled in, not moved
    monkeypatch.setattr("shared.config.settings", s)
    worktree = tmp_path / "var" / "tmp" / "law-0018"
    assert intent_root_for(worktree) == worktree / ".intent"
    assert specs_root_for(worktree) == worktree / ".specs"


# ID: 027ca055-0e6a-44c6-bb65-b4bfab31cd3e
def test_path_resolver_default_follows_the_law_root(d2: tuple[Path, Path]) -> None:
    repo, law = d2
    assert PathResolver(repo).intent_root == law / ".intent"
    assert PathResolver(repo).workers_dir == law / ".intent" / "workers"
    explicit = PathResolver.from_repo(repo, intent_root=Path("/elsewhere"))
    assert explicit.intent_root == Path("/elsewhere")


# ID: 08fd6a14-5a8c-4351-af59-06491ce5899d
def test_law_path_maps_law_constants_onto_the_law_root(d2: tuple[Path, Path]) -> None:
    repo, law = d2
    assert law_path(repo, ".intent/META/enums.json") == law / ".intent/META/enums.json"
    assert law_path(repo, ".specs/papers/X.md") == law / ".specs/papers/X.md"
    assert law_path(repo, "src/a.py") == repo / "src/a.py"


# ID: 49d5735c-25c2-42ee-acde-e5550cd99c3f
def test_configured_repo_root_prefers_an_explicit_repo_path(
    d2: tuple[Path, Path],
) -> None:
    repo, _ = d2  # the fixture runs from a law-less working directory, as D2 does
    assert configured_repo_root() == repo


# ID: ecdae281-0111-437f-82a7-59baf2c11342
def test_configured_repo_root_keeps_cores_law_for_an_external_repo_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An external-target run sets REPO_PATH to the target but starts inside
    CORE's checkout: CORE's law (found from the cwd) still governs loaders
    like the target-class boundaries (regression: 8459f839)."""
    core, target = tmp_path / "core", tmp_path / "target"
    (core / ".intent").mkdir(parents=True)
    target.mkdir()
    monkeypatch.setattr("shared.config.settings", Settings(REPO_PATH=target))
    monkeypatch.chdir(core)
    assert configured_repo_root() == core


# ID: 0bcdeaa2-3e14-40c1-9656-8c3306ab851b
def test_configured_repo_root_without_repo_path_discovers_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".intent").mkdir()
    monkeypatch.setattr("shared.config.settings", Settings())
    monkeypatch.delenv("REPO_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert configured_repo_root() == tmp_path


# ID: b3229530-3116-4329-8940-da417511a579
def test_artifact_gate_finds_the_law_less_clone(d2: tuple[Path, Path]) -> None:
    from mind.logic.engines.artifact_gate import _find_repo_root

    repo, _ = d2
    target = repo / "var" / "prompts" / "x.md"
    assert _find_repo_root(target) == repo.resolve()
    assert _find_repo_root(Path("/nowhere/else/x.md")) is None


# Callers that used to join ".intent"/".specs" on the root themselves
# (ADR-132 D10 · D2 leftovers): under D2 they must find the law beside the
# clone, where the clone itself holds none.


# ID: d71bddac-208a-4c7d-93e5-bd4b612f5f31
def test_cim_signal_sees_the_law_beside_the_clone(d2: tuple[Path, Path]) -> None:
    from body.services.cim.scanners import scan_architectural_signals

    repo, law = d2
    assert scan_architectural_signals(repo).has_intent is False
    (law / ".intent").mkdir(parents=True)
    assert scan_architectural_signals(repo).has_intent is True


# ID: 3feb29eb-9fde-4527-bc10-f43d97b4dc2d
def test_projection_inventory_is_read_from_the_law_root(
    d2: tuple[Path, Path],
) -> None:
    from body.services.representation_coherence_service import _load_inventory

    _, law = d2
    inventory = law / ".intent" / "governance" / "projections.yaml"
    inventory.parent.mkdir(parents=True)
    inventory.write_text("pairs: []\n")
    assert _load_inventory() == {"pairs": []}


# ID: 5fb70b0a-9ce9-405f-b11e-dd884f529cb8
def test_law_facts_reads_decisions_from_the_specs_root(
    d2: tuple[Path, Path],
) -> None:
    from shared.infrastructure.assistant_surface.law_facts import LawFacts

    repo, law = d2
    decisions = law / ".specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "ADR-001-example.md").write_text("# ADR-001\n")
    assert [p.name for p, _ in LawFacts(repo)._adr_files()] == ["ADR-001-example.md"]


# The inverse direction (2026-10-12, first live D2 runtime): naming a law
# file relative to the clone raised ValueError ("not in the subpath"), and
# globbing ".specs/..." on the clone matched nothing.


# ID: ad6ac607-38a0-4554-830d-c79b3e23ebb4
def test_law_relpath_names_law_files_the_way_the_repository_does(
    d2: tuple[Path, Path],
) -> None:
    repo, law = d2
    assert (
        law_relpath(repo, law / ".intent" / "rules" / "a.json")
        == ".intent/rules/a.json"
    )
    assert law_relpath(repo, law / ".specs" / "decisions" / "ADR-1.md") == (
        ".specs/decisions/ADR-1.md"
    )
    assert law_relpath(repo, repo / "src" / "x.py") == "src/x.py"
    assert law_relpath(repo, Path("/elsewhere/y")) == "/elsewhere/y"


# ID: a73c4f8d-7885-430d-a816-c10791ff67e6
def test_law_glob_looks_for_law_patterns_beside_the_clone(
    d2: tuple[Path, Path],
) -> None:
    repo, law = d2
    adr = law / ".specs" / "decisions" / "ADR-1.md"
    adr.parent.mkdir(parents=True)
    adr.write_text("# ADR-1\n")
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("")
    assert law_glob(repo, ".specs/decisions/*.md") == [adr]
    assert law_glob(repo, "src/*.py") == [repo / "src" / "x.py"]


# ID: ceea61c7-dbb8-48d9-b1f1-7229b2c82c47
def test_crawler_sees_law_files_and_names_them_repository_style(
    d2: tuple[Path, Path],
) -> None:
    # Before: the crawler saw no law file under D2 and proposed reaping all
    # of them (the reap_too_large safety rail stopped it).
    from body.services.crawl_service.orchestrator import _resolve_file_artifact_types

    repo, law = d2
    rule = law / ".intent" / "rules" / "a.json"
    rule.parent.mkdir(parents=True)
    rule.write_text("{}")
    found = _resolve_file_artifact_types(
        repo, [(".intent/rules/*.json", "intent_json")]
    )
    assert found == {rule: "intent_json"}
    assert law_relpath(repo, rule) == ".intent/rules/a.json"
