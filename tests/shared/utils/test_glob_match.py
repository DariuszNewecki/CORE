# tests/shared/utils/test_glob_match.py

"""
Tests for src/shared/utils/glob_match.py — gitignore-semantic glob matching.

Coverage targets:
- The four empirical Path.match vs fnmatch mismatches identified in the
  ADR-012 reconnaissance session (security-sensitive under-enforcements
  at redactor and FileNavigator).
- Gitignore boundary semantics: anchored vs unanchored, ** zero-dir,
  ** recursive, trailing '/'.
"""

from __future__ import annotations

from pathlib import Path

from shared.utils.glob_match import matches_any_glob, matches_glob


class TestEmpiricalMismatches:
    """
    Cases where pathlib.Path.match returned the wrong answer on Python
    3.12. matches_glob must return the gitignore-correct answer.
    """

    def test_redactor_deep_nesting_secrets(self):
        # Path.match: False (under-fires). Correct: True.
        assert matches_glob("var/app/secrets/sub/k.txt", "**/secrets/**") is True

    def test_filenavigator_nested_intent_keys(self):
        # Path.match: False (under-fires). Correct: True under gitignore
        # if the pattern is rewritten to '.intent/keys/**' per ADR-012 §5.
        assert matches_glob(".intent/keys/sub/k.txt", ".intent/keys/**") is True

    def test_intentguard_deep_src_under_globstar(self):
        # Path.match: False (under-fires). Correct: True.
        assert matches_glob("src/api/sub/main.py", "src/**/*.py") is True

    def test_filenavigator_secrets_anchored_does_not_match_nested(self):
        # Path.match: True (over-fires by suffix coincidence). Gitignore-
        # correct: False — 'secrets/*' has a middle separator and is
        # therefore root-anchored. Use '**/secrets/**' for any-depth.
        assert matches_glob("var/secrets/k.txt", "secrets/*") is False


class TestGitignoreBoundary:
    """Gitignore-semantic boundary cases."""

    def test_unanchored_no_separator_matches_at_any_depth(self):
        # No separator → unanchored.
        assert matches_glob(".env", ".env") is True
        assert matches_glob("config/.env", ".env") is True
        assert matches_glob("var/app/config/.env", ".env") is True

    def test_globstar_zero_directory(self):
        # '**' must match zero intermediate segments.
        assert matches_glob("src/main.py", "src/**/*.py") is True

    def test_globstar_one_directory(self):
        assert matches_glob("src/api/main.py", "src/**/*.py") is True

    def test_globstar_many_directories(self):
        assert matches_glob("src/a/b/c/main.py", "src/**/*.py") is True

    def test_anchored_single_star_matches_immediate_child(self):
        # 'src/*' matches direct children of src.
        assert matches_glob("src/main.py", "src/*") is True

    def test_anchored_single_star_recursive_via_directory_inheritance(self):
        # Under gitignore semantics, when 'src/*' matches the directory
        # 'src/api', everything under that directory is implicitly matched
        # by the directory-inheritance shadow rule (gitignore.5).
        # Practical implication: anchored single-segment patterns like
        # 'src/*' behave recursively as forbid-patterns.
        assert matches_glob("src/api/main.py", "src/*") is True

    def test_double_globstar_anywhere(self):
        # '**/X/**' matches X at any depth, with anything below.
        assert matches_glob("var/secrets/k.txt", "**/secrets/**") is True
        assert matches_glob("a/b/secrets/c/d.txt", "**/secrets/**") is True
        assert matches_glob("secrets/k.txt", "secrets/**") is True

    def test_trailing_slash_directory_only(self):
        # In pathspec, trailing '/' restricts the pattern to directories.
        # We test the practical effect on path strings that look like dirs
        # via their trailing component. The library handles the dir
        # restriction via filesystem semantics; for pure-path matching
        # we just confirm consistent behavior.
        assert matches_glob("var/cache/", "**/cache/") is True


class TestEdgeCases:
    """Empty inputs, Path objects, Windows-style paths."""

    def test_empty_pattern_returns_false(self):
        assert matches_glob("anything.py", "") is False

    def test_path_object_input(self):
        assert matches_glob(Path("src/main.py"), "src/**/*.py") is True

    def test_windows_style_path_normalized(self):
        # Backslashes converted to forward slashes for matching.
        assert matches_glob("src\\api\\main.py", "src/**/*.py") is True


class TestMatchesAnyGlob:
    def test_any_returns_true_on_first_match(self):
        patterns = ["**/.env", "**/secrets/**"]
        assert matches_any_glob("var/secrets/k.txt", patterns) is True

    def test_any_returns_false_when_none_match(self):
        patterns = ["**/.env", "**/secrets/**"]
        assert matches_any_glob("src/main.py", patterns) is False

    def test_any_with_empty_pattern_list(self):
        assert matches_any_glob("src/main.py", []) is False
