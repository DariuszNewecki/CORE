# src/shared/infrastructure/intent/test_coverage_paths.py
"""
Source-to-test path mapping helper.

Single source of truth for mapping repo-relative source paths to their
governed repo-relative test paths. Both the mapping rule and the
filename conventions are owned by
.intent/enforcement/config/test_coverage.yaml.

Authority: policy. The governing document is
.intent/enforcement/config/test_coverage.yaml, accessed exclusively via
IntentRepository. No other module may hardcode the source->test
mapping — all call sites route through this helper.

The _FALLBACK_* constants below are last-resort graceful degradation
for the narrow case where the policy document cannot be loaded (e.g.
bootstrap races, corrupt YAML). They MUST NOT be treated as
defaults-in-logic — when the policy loads successfully, it always wins.

LAYER: shared/infrastructure/intent — pure helper. No imports from
will/, body/, or cli/.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c3f8a2d6-1e4b-4c79-9a5d-8b6f0e1d2c3a
class InstrumentUnavailable(Exception):
    """Raised when a coverage scan cannot actually run — the input source is
    unreachable (missing/misconfigured source root), so an empty result would
    be "couldn't look", not "genuinely clean" (#765/T1.3). Callers translate
    this into a post_unavailable observation rather than a false all-clear."""


_FALLBACK_SOURCE_ROOT = "src"
_FALLBACK_TEST_ROOT = "tests"
_FALLBACK_TEST_FILE_SUFFIX = "/test_generated.py"
_FALLBACK_EXCLUDED_FILENAMES: list[str] = ["__init__.py"]


# ID: 6d7e2c9a-4b5f-4801-9e13-a2b3c4d5e6f7
def load_test_coverage_config() -> dict[str, Any]:
    """
    Load .intent/enforcement/config/test_coverage.yaml via IntentRepository.

    Returns the parsed policy dict on success. On any failure — missing
    file, parse error, unexpected top-level type — returns fallback
    defaults and logs a warning so callers degrade gracefully rather
    than halting.
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/test_coverage.yaml")
        config = repo.load_document(config_path)
        if isinstance(config, dict):
            return config
        logger.warning(
            "test_coverage_paths: test_coverage.yaml did not parse as a dict "
            "— using fallback defaults."
        )
    except Exception as exc:
        logger.warning(
            "test_coverage_paths: could not load .intent/enforcement/config/"
            "test_coverage.yaml (%s) — using fallback defaults.",
            exc,
        )
    return {
        "source_root": _FALLBACK_SOURCE_ROOT,
        "test_root": _FALLBACK_TEST_ROOT,
        "test_file_suffix": _FALLBACK_TEST_FILE_SUFFIX,
        "excluded_filenames": list(_FALLBACK_EXCLUDED_FILENAMES),
    }


# ID: 7e8f3d0b-5c6a-4912-af24-b3c4d5e6f708
def source_to_test_path(
    source_file: str,
    config: dict[str, Any] | None = None,
) -> str:
    """
    Map a repo-relative source path to its governed repo-relative test path.

    Mapping:
        {source_root}/foo/bar.py
          -> {test_root}/foo/bar{test_file_suffix}

    Args:
        source_file: repo-relative path to a Python source file, e.g.
            "src/foo/bar.py". Callers must pass repo-relative paths.
        config: optional pre-loaded policy dict. If None,
            load_test_coverage_config() is invoked.

    Returns:
        Repo-relative path to the governed test file, e.g.
            "tests/foo/bar/test_generated.py".

    Raises:
        ValueError: if source_file does not start with "{source_root}/", or
            contains a ".." path segment (#817 — the prefix check alone is
            textual, so "src/../../../etc/passwd" passes it while resolving
            well outside source_root; callers that need actual filesystem
            containment against a repo_root should use
            resolve_contained_source_path instead/in addition).
    """
    if config is None:
        config = load_test_coverage_config()

    source_root: str = config.get("source_root", _FALLBACK_SOURCE_ROOT)
    test_root: str = config.get("test_root", _FALLBACK_TEST_ROOT)
    test_file_suffix: str = config.get("test_file_suffix", _FALLBACK_TEST_FILE_SUFFIX)

    prefix = f"{source_root}/"
    if not source_file.startswith(prefix):
        raise ValueError(
            f"source_file {source_file!r} does not start with configured "
            f"source_root prefix {prefix!r}"
        )
    if ".." in PurePosixPath(source_file).parts:
        raise ValueError(
            f"source_file {source_file!r} contains '..' path segments — "
            "traversal outside source_root is not permitted"
        )

    return (
        source_file.replace(prefix, f"{test_root}/", 1).removesuffix(".py")
        + test_file_suffix
    )


# ID: 6160b527-a734-4501-9804-18c299228a5b
def resolve_contained_source_path(repo_root: Path, source_file: str) -> Path:
    """Resolve `source_file` against `repo_root`, rejecting any traversal
    outside it (#817).

    A bare `(repo_root / source_file).resolve()` does not, by itself, reject
    a result outside `repo_root` — `resolve()` only normalizes `..`
    segments, it does not bound the result. `source_to_test_path`'s textual
    prefix check catches this for callers that map source_file to a test
    path, but several existence-check call sites (does this source file
    exist on disk?) resolve and check `source_file` directly, before any
    call to `source_to_test_path` — those call sites need this helper
    instead, or in addition.

    Raises:
        ValueError: the resolved path is not contained within `repo_root`.
    """
    repo_root = repo_root.resolve()
    resolved = (repo_root / source_file).resolve()
    if not resolved.is_relative_to(repo_root):
        raise ValueError(
            f"source_file {source_file!r} resolves outside repo_root "
            f"({resolved} is not within {repo_root})"
        )
    return resolved


# ID: fef2a66e-f052-45e1-ac25-db1d90d26695
def test_file_ancestor_init_paths(test_file: str) -> list[str]:
    """Repo-relative `__init__.py` paths from `test_file`'s directory up
    through `tests/`, inclusive.

    Mirrors `body.atomic.build_test_for_symbol_action`'s ancestor-walk
    exactly — including its hardcoded `"tests"` stop condition (that action
    does not consult the configured `test_root`; this mirrors it as-is
    rather than introducing a second, possibly-divergent source of truth).
    build.test_for_symbol creates any of these that are missing so
    pytest/importlib can resolve the generated test's module path, and
    declares them in `files_produced` alongside the test file itself — a
    caller that needs to know the *full* candidate footprint of a
    build.test_for_symbol write (not just the test file) for checkpoint/
    restore purposes needs this list too. Pure path arithmetic, no I/O —
    does not check which of these actually exist or would actually be
    created; callers combine this with their own existence checks (or a
    Body-layer checkpoint) as needed.
    """
    ancestor = PurePosixPath(test_file).parent
    paths: list[str] = []
    while True:
        paths.append(str(ancestor / "__init__.py"))
        if str(ancestor) == "tests":
            break
        parent = ancestor.parent
        if parent == ancestor:
            break
        ancestor = parent
    return paths


# ID: 8f9a4e1c-6d7b-4a23-be35-c4d5e6f7a819
def uncovered_source_files(
    repo_root: Path,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """
    Walk source_root and return repo-relative paths for in-scope Python
    source files that have no corresponding test file.

    Shared between TestCoverageSensor (which posts
    `python::test.coverage::*` for these sources) and TestRunnerSensor (which
    uses the same set as current_subjects for the
    `python::test.runner.missing` quarantine drain — ADR-072 D5).

    The mapping and scoping rules are entirely owned by
    .intent/enforcement/config/test_coverage.yaml:
      - source_root, test_root, test_file_suffix
      - excluded_filenames (skip-list)
      - include_files (scope limiter; if non-empty, only these are scanned)
    """
    if config is None:
        config = load_test_coverage_config()

    source_root_rel: str = config.get("source_root", _FALLBACK_SOURCE_ROOT)
    excluded: frozenset[str] = frozenset(
        config.get("excluded_filenames", _FALLBACK_EXCLUDED_FILENAMES)
    )
    include_files: frozenset[str] = frozenset(config.get("include_files") or [])

    src_root = repo_root / source_root_rel
    if not src_root.exists():
        # #765/T1.3: an empty scan here is "couldn't look", not "all covered".
        # Previously this returned [] and both callers read it as a genuine
        # all-clear — TestCoverageSensor posting "all files covered" and
        # TestRunnerSensor resolving quarantined 'missing' findings as if the
        # sources were now covered. Raise so callers post_unavailable instead.
        raise InstrumentUnavailable(
            f"coverage source root not found at {src_root} "
            f"(source_root={source_root_rel!r})"
        )

    uncovered: list[str] = []

    for py_file in src_root.rglob("*.py"):
        if py_file.name in excluded:
            continue

        rel = py_file.relative_to(repo_root)
        source_file = str(rel)

        if include_files and source_file not in include_files:
            continue

        try:
            test_rel = source_to_test_path(source_file, config)
        except ValueError:
            continue

        test_path = repo_root / test_rel

        if not test_path.exists():
            uncovered.append(source_file)

    return uncovered
