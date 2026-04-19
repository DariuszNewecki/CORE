# src/shared/infrastructure/intent/test_coverage_paths.py
# ID: shared.infrastructure.intent.test_coverage_paths
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

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

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
        ValueError: if source_file does not start with "{source_root}/".
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

    return (
        source_file.replace(prefix, f"{test_root}/", 1).removesuffix(".py")
        + test_file_suffix
    )
