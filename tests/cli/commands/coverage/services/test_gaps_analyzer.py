# tests/cli/commands/coverage/services/test_gaps_analyzer.py

"""Tests for GapsAnalyzer.find_gaps — #774 (ADR-040 sweep) coverage drift fix.

Source: cli.commands.coverage.services.gaps_analyzer

Prior local constants (_DEFAULT_GAP_THRESHOLD_PCT, _DEFAULT_LOW_BUCKET_PCT)
duplicated the governed coverage.gap_threshold_pct / coverage.low_bucket_pct
values instead of reading them. This file's own values happened to match
today (75.0 / 50.0), but the sibling check_commands.py's equivalent
_WARN_PCT_DEFAULT had already drifted to 80.0 against the governed 75 --
same duplication pattern, already a real bug in one of the two files.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from cli.commands.coverage.services.gaps_analyzer import _CFG, GapsAnalyzer


async def test_find_gaps_default_threshold_matches_governed_config() -> None:
    """The default threshold must be the governed value, not a local
    duplicate that can independently drift."""
    analyzer = GapsAnalyzer(repo_root=Path("/repo"))
    with patch.object(
        analyzer, "get_coverage_map", new=AsyncMock(return_value={"a.py": 60.0})
    ):
        result = await analyzer.find_gaps()

    assert result["stats"]["threshold"] == _CFG.gap_threshold_pct


async def test_find_gaps_below_50_uses_governed_low_bucket_pct() -> None:
    analyzer = GapsAnalyzer(repo_root=Path("/repo"))
    coverage_map = {
        "below.py": _CFG.low_bucket_pct - 1,
        "above.py": _CFG.low_bucket_pct + 1,
    }
    with patch.object(
        analyzer, "get_coverage_map", new=AsyncMock(return_value=coverage_map)
    ):
        result = await analyzer.find_gaps(threshold=100.0)

    assert result["stats"]["below_50"] == 1


async def test_find_gaps_empty_coverage_map_returns_zeroed_stats() -> None:
    analyzer = GapsAnalyzer(repo_root=Path("/repo"))
    with patch.object(
        analyzer, "get_coverage_map", new=AsyncMock(return_value={})
    ):
        result = await analyzer.find_gaps()

    assert result == {
        "below_threshold": [],
        "sorted_lowest": [],
        "stats": {"total": 0, "below_threshold": 0, "below_50": 0},
    }
