"""``core-admin database recount`` (#1114): the hand count of findings.

The row counter is checked on its own here; the integration test runs it
against CORE's two queries on a real database.
"""

from __future__ import annotations

import datetime as dt

from cli.resources.database.recount import _count


START = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
BEFORE = START - dt.timedelta(days=1)
AFTER = START + dt.timedelta(days=1)


def test_counts_by_each_figures_own_time() -> None:
    rows = [
        ("a::1", "open", AFTER, AFTER, None),
        ("a::2", "resolved", BEFORE, AFTER, AFTER),  # resolved in the window
        ("a::3", "resolved", BEFORE, AFTER, BEFORE),  # touched, resolved before
        ("a::4", "abandoned", BEFORE, AFTER, None),
        ("loop_hold.sample::x", "abandoned", AFTER, AFTER, None),
    ]
    counts = _count(rows, START, ("loop_hold.sample::",), inclusive=True)
    assert counts == {
        "created": 1,
        "resolved": 1,
        "abandoned": 1,
        "telemetry_excluded": 1,
    }


def test_the_window_edge_follows_the_measure() -> None:
    rows = [("a::1", "open", START, START, None)]
    assert _count(rows, START, (), inclusive=True)["created"] == 1
    assert _count(rows, START, (), inclusive=False)["created"] == 0
