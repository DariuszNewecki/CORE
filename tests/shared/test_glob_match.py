# Tests for src/shared/utils/glob_match.py

from __future__ import annotations

from pathlib import Path

from shared.utils.glob_match import matches_any_glob, matches_glob


def test_matches_glob_basic_relative_path():
    assert matches_glob("src/main.py", "src/**/*.py") is True


def test_matches_glob_nested_relative_path():
    assert matches_glob("src/api/sub/main.py", "src/**/*.py") is True


def test_matches_glob_double_star_segments():
    assert matches_glob("var/secrets/k.txt", "**/secrets/**") is True


def test_matches_glob_single_star_does_not_cross_segments():
    assert matches_glob("var/secrets/k.txt", "secrets/*") is False


def test_matches_glob_empty_pattern_returns_false():
    assert matches_glob("src/main.py", "") is False


def test_matches_glob_path_object_input():
    assert matches_glob(Path("src/main.py"), "src/**/*.py") is True


def test_matches_glob_normalizes_leading_slash():
    assert matches_glob("/src/main.py", "src/**/*.py") is True


def test_matches_glob_normalizes_leading_dot_slash():
    assert matches_glob("./src/main.py", "src/**/*.py") is True


def test_matches_glob_normalizes_multiple_leading_slashes():
    assert matches_glob("//src/main.py", "src/**/*.py") is True


def test_matches_glob_normalizes_absolute_path_object():
    assert matches_glob(Path("/src/main.py"), "src/**/*.py") is True


def test_matches_glob_negative_preserved_after_normalization():
    assert matches_glob("/var/secrets/k.txt", "secrets/*") is False


def test_matches_any_glob_matches_one_pattern():
    assert matches_any_glob("var/secrets/k.txt", ["**/.env", "**/secrets/**"]) is True


def test_matches_any_glob_matches_no_pattern():
    assert matches_any_glob("src/main.py", ["**/.env", "**/secrets/**"]) is False


def test_matches_any_glob_normalizes_leading_slash():
    assert matches_any_glob("/var/secrets/k.txt", ["**/.env", "**/secrets/**"]) is True
