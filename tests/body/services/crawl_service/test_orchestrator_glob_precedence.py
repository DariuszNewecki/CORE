# tests/body/services/crawl_service/test_orchestrator_glob_precedence.py
"""Glob-precedence resolution for overlapping artifact_type discovery globs
(#786).

A file matched by two globs must be assigned the most-specific glob's type,
deterministically — not whichever registry scope was processed last. The
canonical failure: .intent/architecture/bridges/*.yaml matches both
architecture_bridge's specific glob and intent_yaml's broad .intent/**
glob, and was frozen as whichever won a given crawl pass.
"""

from __future__ import annotations

from pathlib import Path

from body.services.crawl_service.orchestrator import (
    _glob_specificity,
    _resolve_file_artifact_types,
)


def test_specificity_prefers_longer_literal_prefix() -> None:
    specific = _glob_specificity(".intent/architecture/bridges/**/*.yaml")
    broad = _glob_specificity(".intent/**/*.yaml")
    assert specific > broad


def test_specificity_counts_prefix_before_first_wildcard() -> None:
    assert _glob_specificity("src/**/*.py") == len("src/")
    assert _glob_specificity("a/b/c.yaml") == len("a/b/c.yaml")  # no wildcard
    assert _glob_specificity("*.py") == 0


def test_overlapping_globs_resolve_to_most_specific(tmp_path: Path) -> None:
    """The exact #786 scenario: a file under a specific subdir matched by both
    a broad and a specific glob resolves to the specific type."""
    bridges = tmp_path / ".intent" / "architecture" / "bridges"
    bridges.mkdir(parents=True)
    (bridges / "worker.yaml").write_text("x: 1\n", encoding="utf-8")
    other = tmp_path / ".intent" / "cim"
    other.mkdir(parents=True)
    (other / "thresholds.yaml").write_text("y: 2\n", encoding="utf-8")

    # Deliberately list the BROAD glob first — under the old last-wins loop
    # this ordering would have frozen the bridge file as intent_yaml.
    scopes = [
        (".intent/**/*.yaml", "intent_yaml"),
        (".intent/architecture/bridges/**/*.yaml", "architecture_bridge"),
    ]
    resolved = _resolve_file_artifact_types(tmp_path, scopes)

    assert resolved[bridges / "worker.yaml"] == "architecture_bridge"
    assert resolved[other / "thresholds.yaml"] == "intent_yaml"


def test_specific_glob_first_still_resolves_correctly(tmp_path: Path) -> None:
    """Order-independence: reversing the scope order gives the same result."""
    bridges = tmp_path / ".intent" / "architecture" / "bridges"
    bridges.mkdir(parents=True)
    (bridges / "worker.yaml").write_text("x: 1\n", encoding="utf-8")

    scopes = [
        (".intent/architecture/bridges/**/*.yaml", "architecture_bridge"),
        (".intent/**/*.yaml", "intent_yaml"),
    ]
    resolved = _resolve_file_artifact_types(tmp_path, scopes)
    assert resolved[bridges / "worker.yaml"] == "architecture_bridge"


def test_each_file_appears_once(tmp_path: Path) -> None:
    """The resolver returns a dict keyed by path, so a doubly-matched file
    appears exactly once (the old loop processed it once per matching glob)."""
    d = tmp_path / ".intent" / "architecture" / "bridges"
    d.mkdir(parents=True)
    (d / "w.yaml").write_text("x: 1\n", encoding="utf-8")
    scopes = [
        (".intent/**/*.yaml", "intent_yaml"),
        (".intent/architecture/bridges/**/*.yaml", "architecture_bridge"),
    ]
    resolved = _resolve_file_artifact_types(tmp_path, scopes)
    # dict semantics guarantee uniqueness; assert the one file is present once
    matching = [p for p in resolved if p.name == "w.yaml"]
    assert len(matching) == 1


def test_non_matching_files_excluded(tmp_path: Path) -> None:
    (tmp_path / ".intent").mkdir()
    (tmp_path / ".intent" / "readme.md").write_text("# not yaml\n", encoding="utf-8")
    scopes = [(".intent/**/*.yaml", "intent_yaml")]
    resolved = _resolve_file_artifact_types(tmp_path, scopes)
    assert resolved == {}
