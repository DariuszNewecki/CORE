"""F-10.1b — exit code constants regression guard.

The values are part of the CI gate's public contract. External branch
protection rules and pre-commit hook chains read these codes to decide
whether to merge-block, prompt, or pass. Changing a value silently is
a constitutional issue: an existing CI rule wired to "block on 1" would
fail to block on findings if EXIT_FINDINGS changed.

This test fails loudly if any constant drifts. Changing one of these
values requires an ADR amendment (per ADR-085 §D5 listing F-10's
merge-blocking semantics as the exit criterion).
"""

from __future__ import annotations

from cli.utils.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_FINDINGS,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
)


def test_exit_ok_is_zero() -> None:
    """0 = success per Unix convention. Cannot drift."""
    assert EXIT_OK == 0


def test_exit_findings_is_one() -> None:
    """1 = expected failure. Matches every pre-existing `typer.Exit(1)`."""
    assert EXIT_FINDINGS == 1


def test_exit_config_error_is_two() -> None:
    """2 = misuse / configuration error. sysexits.h EX_USAGE convention."""
    assert EXIT_CONFIG_ERROR == 2


def test_exit_internal_error_is_sixty_four() -> None:
    """64 = sysexits.h reserved internal-error range start."""
    assert EXIT_INTERNAL_ERROR == 64


def test_all_codes_are_distinct() -> None:
    """No two codes collide — the gate must surface distinct failure shapes."""
    codes = {EXIT_OK, EXIT_FINDINGS, EXIT_CONFIG_ERROR, EXIT_INTERNAL_ERROR}
    assert len(codes) == 4
