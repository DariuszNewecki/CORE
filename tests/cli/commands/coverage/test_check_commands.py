# tests/cli/commands/coverage/test_check_commands.py

"""Regression guard for #774 (ADR-040 sweep): check_commands.py previously
duplicated coverage.{gap_threshold_pct,low_bucket_pct,warn_pct} as local
constants instead of reading them, and one of the three had already
drifted -- _WARN_PCT_DEFAULT = 80.0 in src/ vs. the governed warn_pct: 75.
This pins the module's config to the governed values so the duplication
(and the drift it enabled) can't silently reappear.

Source: cli.commands.coverage.check_commands
"""

from __future__ import annotations

from cli.commands.coverage.check_commands import _CFG


def test_gap_threshold_pct_matches_governed_config() -> None:
    assert _CFG.gap_threshold_pct == 75.0


def test_low_bucket_pct_matches_governed_config() -> None:
    assert _CFG.low_bucket_pct == 50


def test_warn_pct_matches_governed_config_not_the_old_drifted_value() -> None:
    """The actual drift this issue found: src/ said 80.0, the governed
    config said 75. Pin the real value so a re-introduced local constant
    can't quietly diverge from it again."""
    assert _CFG.warn_pct == 75
    assert _CFG.warn_pct != 80.0
