# tests/shared/infrastructure/intent/test_coverage_paths__sibling_test_paths.py
"""sibling_test_paths: existing tests that exercise the same source module."""

from __future__ import annotations

from pathlib import Path

from shared.infrastructure.intent.test_coverage_paths import sibling_test_paths


_CONFIG = {
    "source_root": "src",
    "test_root": "tests",
    "test_file_suffix": "/test_generated.py",
}


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")


# ID: 02f7cb82-25f3-4975-97e5-3bc24f115870
def test_finds_hand_written_and_module_dir_siblings(tmp_path: Path) -> None:
    _touch(tmp_path, "tests/mind/engines/registry/test_generated.py")
    _touch(tmp_path, "tests/mind/engines/registry/test_extra.py")
    _touch(tmp_path, "tests/mind/engines/test_registry.py")
    _touch(tmp_path, "tests/mind/engines/test_registry__EngineRegistry.py")
    _touch(tmp_path, "tests/mind/engines/test_registryx.py")
    _touch(tmp_path, "tests/mind/engines/test_base__BaseEngine.py")
    _touch(tmp_path, "tests/mind/engines/registry/conftest.py")

    result = sibling_test_paths(tmp_path, "src/mind/engines/registry.py", _CONFIG)

    assert result == [
        "tests/mind/engines/registry/test_extra.py",
        "tests/mind/engines/test_registry.py",
        "tests/mind/engines/test_registry__EngineRegistry.py",
    ]


# ID: 814f6f31-ec31-4823-b21b-d01614b2b750
def test_empty_when_no_tests_exist(tmp_path: Path) -> None:
    assert sibling_test_paths(tmp_path, "src/mind/engines/registry.py", _CONFIG) == []


# ID: 639c8187-f659-4612-b392-49397c772969
def test_empty_when_mapping_refused(tmp_path: Path) -> None:
    assert sibling_test_paths(tmp_path, "lib/outside.py", _CONFIG) == []
