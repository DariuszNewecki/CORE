"""Regression tests for the target-class taxonomy loader.

Pins three behaviors:
- Every declared boundary classifies its example paths correctly.
- The substring bug ADR-097 D2 names is structurally foreclosed:
  a path containing 'src/' as a sub-segment under var/tmp/ resolves
  to ephemeral-scratch, NOT repo-source.
- Fail-closed semantics: malformed YAML, missing enum, drift between
  the YAML's target_class values and the enum, and bad default all
  raise TargetClassBoundariesError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.infrastructure.intent.target_class import (
    TargetClassBoundariesError,
    load_target_class_boundaries,
    reset_target_class_cache,
    resolve_target_class,
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Drop module-level cache between tests so each test sees a fresh load."""
    reset_target_class_cache()
    yield
    reset_target_class_cache()


# ---------------------------------------------------------------------------
# Live-data classification: against the real .intent/ taxonomy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path, expected_class",
    [
        # repo-source — commit-bearing source files
        ("src/foo.py", "repo-source"),
        ("src/body/atomic/executor.py", "repo-source"),
        ("tests/test_x.py", "repo-source"),
        ("tests/shared/infrastructure/intent/test_target_class.py", "repo-source"),
        # repo-source via default fallback — top-level repo files
        ("pyproject.toml", "repo-source"),
        ("README.md", "repo-source"),
        ("CLAUDE.md", "repo-source"),
        # runtime-output — operational output
        ("reports/audit/2026.json", "runtime-output"),
        ("var/cache/embeddings/abc.bin", "runtime-output"),
        ("var/logs/daemon.log", "runtime-output"),
        ("var/workflows/pending_writes/pw-123.json", "runtime-output"),
        # ephemeral-scratch — transient writes under var/tmp/
        ("var/tmp/sandbox_xxx/test_y.py", "ephemeral-scratch"),
        ("var/tmp/core-shadow-abc/shadow/src/foo.py", "ephemeral-scratch"),
        # governed-artifact — governance-bearing files
        (".intent/rules/architecture/layer_separation.json", "governed-artifact"),
        (".specs/decisions/ADR-097.md", "governed-artifact"),
        (".intent/META/enums.json", "governed-artifact"),
    ],
)
def test_resolve_classifies_path(rel_path: str, expected_class: str) -> None:
    """Every named path classifies into the expected target_class."""
    assert resolve_target_class(rel_path) == expected_class


def test_substring_bug_foreclosed_by_ordering() -> None:
    """Core motivation of ADR-097 D2: a path that CONTAINS 'src/' as a
    sub-segment under var/tmp/ classifies as ephemeral-scratch, NOT
    repo-source. This is the bug the path-aware dispatch fixes."""
    path = "var/tmp/core-shadow-uuid/shadow/src/body/atomic/executor.py"
    result = resolve_target_class(path)
    assert result == "ephemeral-scratch", (
        f"Substring-bug guard failed: {path!r} should classify as "
        f"ephemeral-scratch (var/tmp/ prefix match wins over src/), "
        f"got {result!r}. Ordering in target_class_boundaries.yaml "
        f"must keep var/tmp/ before src/."
    )


def test_governed_artifact_precedence_over_src() -> None:
    """`.intent/` and `.specs/` are listed BEFORE src/ in the boundaries
    so governance-bearing paths never fall through to repo-source."""
    assert resolve_target_class(".intent/foo.yaml") == "governed-artifact"
    assert resolve_target_class(".specs/decisions/x.md") == "governed-artifact"


def test_dot_slash_prefix_stripped() -> None:
    """./foo classifies same as foo (mirrors FileHandler's normalization)."""
    assert resolve_target_class("./src/foo.py") == "repo-source"
    assert resolve_target_class("./var/tmp/x.py") == "ephemeral-scratch"


def test_default_falls_back_to_repo_source() -> None:
    """Paths matching no declared prefix fall through to the default.
    ADR-097 D2 third rule: fail-safe toward the strictest validation set."""
    # Some hypothetical top-level file not enumerated as a prefix.
    assert resolve_target_class("unknown_root_file.txt") == "repo-source"


# ---------------------------------------------------------------------------
# Loader structural contract
# ---------------------------------------------------------------------------


def test_load_target_class_boundaries_returns_non_empty() -> None:
    """The live taxonomy must have at least one boundary and a default."""
    b = load_target_class_boundaries()
    assert len(b.boundaries) > 0
    assert b.default in {
        "repo-source",
        "runtime-output",
        "ephemeral-scratch",
        "governed-artifact",
    }


def test_every_boundary_target_class_is_in_enum() -> None:
    """Every loaded boundary's target_class value is from the enum set.
    The loader enforces this at load time; this test pins that contract."""
    b = load_target_class_boundaries()
    valid = {"repo-source", "runtime-output", "ephemeral-scratch", "governed-artifact"}
    for entry in b.boundaries:
        assert entry.target_class in valid, (
            f"Boundary {entry.prefix!r} → {entry.target_class!r} "
            f"is not in the target_class enum."
        )


# ---------------------------------------------------------------------------
# Fail-closed semantics: synthetic repo roots with broken inputs
# ---------------------------------------------------------------------------


def _build_minimal_repo(
    root: Path,
    boundaries_yaml: str,
    enum_values: list[str] | None = None,
) -> None:
    """Materialize a minimal .intent/ tree at root with the given YAML
    and an enums.json that ships the standard target_class enum unless
    overridden."""
    (root / ".intent" / "taxonomies").mkdir(parents=True)
    (root / ".intent" / "META").mkdir(parents=True)
    (root / ".intent" / "taxonomies" / "target_class_boundaries.yaml").write_text(
        boundaries_yaml, encoding="utf-8"
    )
    enum = (
        enum_values
        if enum_values is not None
        else [
            "repo-source",
            "runtime-output",
            "ephemeral-scratch",
            "governed-artifact",
        ]
    )
    enums_doc = {
        "definitions": {
            "target_class": {
                "type": "string",
                "enum": enum,
            }
        }
    }
    (root / ".intent" / "META" / "enums.json").write_text(
        json.dumps(enums_doc, indent=2), encoding="utf-8"
    )


def test_load_raises_on_missing_yaml(tmp_path: Path) -> None:
    """No file at .intent/taxonomies/target_class_boundaries.yaml → raise."""
    (tmp_path / ".intent" / "META").mkdir(parents=True)
    (tmp_path / ".intent" / "META" / "enums.json").write_text(
        json.dumps({"definitions": {"target_class": {"enum": ["repo-source"]}}}),
        encoding="utf-8",
    )
    with pytest.raises(TargetClassBoundariesError, match="boundaries missing"):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_missing_enum_file(tmp_path: Path) -> None:
    """No file at .intent/META/enums.json → raise."""
    (tmp_path / ".intent" / "taxonomies").mkdir(parents=True)
    (tmp_path / ".intent" / "taxonomies" / "target_class_boundaries.yaml").write_text(
        "boundaries:\n  - prefix: 'src/'\n    target_class: repo-source\ndefault: repo-source\n",
        encoding="utf-8",
    )
    with pytest.raises(TargetClassBoundariesError, match="enum file missing"):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_malformed_yaml(tmp_path: Path) -> None:
    """YAML parse failure → raise."""
    _build_minimal_repo(tmp_path, ":\n:not yaml:")
    with pytest.raises(
        TargetClassBoundariesError, match=r"malformed YAML|must be a mapping"
    ):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_target_class_drift(tmp_path: Path) -> None:
    """A boundary's target_class value not in the enum → raise."""
    yaml_text = (
        "boundaries:\n"
        "  - prefix: 'src/'\n"
        "    target_class: not-a-real-class\n"
        "default: repo-source\n"
    )
    _build_minimal_repo(tmp_path, yaml_text)
    with pytest.raises(
        TargetClassBoundariesError, match="not in the target_class enum"
    ):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_unknown_field(tmp_path: Path) -> None:
    """Extra keys in a boundary entry → raise (fail-closed strictness)."""
    yaml_text = (
        "boundaries:\n"
        "  - prefix: 'src/'\n"
        "    target_class: repo-source\n"
        "    extra_field: nope\n"
        "default: repo-source\n"
    )
    _build_minimal_repo(tmp_path, yaml_text)
    with pytest.raises(TargetClassBoundariesError, match="unknown field"):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_missing_default(tmp_path: Path) -> None:
    """No 'default:' key → raise."""
    yaml_text = "boundaries:\n  - prefix: 'src/'\n    target_class: repo-source\n"
    _build_minimal_repo(tmp_path, yaml_text)
    with pytest.raises(TargetClassBoundariesError, match="'default:'"):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_bad_default(tmp_path: Path) -> None:
    """Default value not in enum → raise."""
    yaml_text = (
        "boundaries:\n"
        "  - prefix: 'src/'\n"
        "    target_class: repo-source\n"
        "default: not-a-real-class\n"
    )
    _build_minimal_repo(tmp_path, yaml_text)
    with pytest.raises(
        TargetClassBoundariesError, match=r"default=.*not in the target_class enum"
    ):
        load_target_class_boundaries(tmp_path)


def test_load_raises_on_empty_boundaries(tmp_path: Path) -> None:
    """Empty boundaries list → raise (silent pass-all would defeat the dispatch)."""
    yaml_text = "boundaries: []\ndefault: repo-source\n"
    _build_minimal_repo(tmp_path, yaml_text)
    with pytest.raises(TargetClassBoundariesError, match="must be a non-empty list"):
        load_target_class_boundaries(tmp_path)
