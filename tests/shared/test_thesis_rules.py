"""The thesis rules (DECISIONS.md, "Thesis and baselines (2026-10-13)")."""

from __future__ import annotations

from datetime import date, timedelta

from shared.thesis_rules import (
    ThesisMeasures,
    breaches,
    report_line,
    week_label,
)


DAY = date(2026, 11, 20)


def _m(day=DAY, unverified=0, ai=0.7, waste=1.5, conv=0.9) -> ThesisMeasures:
    return ThesisMeasures(day, unverified, ai, waste, conv)


def _broken(today, history=()) -> set[str]:
    return {b.measure for b in breaches(today, list(history))}


def test_the_baseline_day_breaks_nothing() -> None:
    assert _broken(ThesisMeasures(date(2026, 10, 13), 0, 0.63, 2.0, 0.89)) == set()


def test_any_unverified_write_breaks() -> None:
    assert _broken(_m(unverified=1)) == {"unverified_writes"}


def test_the_unverified_message_names_the_deploy_after_the_cutover() -> None:
    """After the promotion cutover the writes that count are deploys: the
    message says so, not only 'reached main'."""
    [breach] = breaches(_m(unverified=4), [])
    assert breach.message.startswith("4 unverified write(s) since 2026-10-12")
    assert "deploy without the governor's approval of that exact promotion" in (
        breach.message
    )


def test_ai_share_below_63_percent_breaks() -> None:
    assert _broken(_m(ai=0.62)) == {"ai_share"}
    assert _broken(_m(ai=0.63)) == set()


def test_waste_must_not_rise_against_a_month_earlier() -> None:
    month_ago = _m(day=DAY - timedelta(days=30), waste=1.2)
    assert _broken(_m(waste=1.3), [month_ago]) == {"waste_per_change"}
    assert _broken(_m(waste=1.2), [month_ago]) == set()
    # Before a month of history, the 2.0 baseline is the reference.
    assert _broken(_m(waste=2.1)) == {"waste_per_change"}
    assert _broken(_m(waste=2.0)) == set()


def test_convergence_breaks_only_two_months_below_after_reaching_100() -> None:
    never = [_m(day=DAY - timedelta(days=30), conv=0.8)]
    assert _broken(_m(conv=0.8), never) == set()  # never reached 100%
    reached = _m(day=DAY - timedelta(days=60), conv=1.02)
    below = _m(day=DAY - timedelta(days=30), conv=0.95)
    assert _broken(_m(conv=0.9), [reached, below]) == {"convergence"}
    recovered = _m(day=DAY - timedelta(days=30), conv=1.0)
    assert _broken(_m(conv=0.9), [reached, recovered]) == set()  # one month only


def test_an_unreadable_measure_never_breaks() -> None:
    assert _broken(ThesisMeasures(DAY, None, None, None, None)) == set()


def test_todays_own_record_is_not_its_history() -> None:
    assert _broken(_m(waste=1.0), [_m(waste=0.5)]) == set()


def test_report_line_and_week() -> None:
    line = report_line(ThesisMeasures(date(2026, 10, 13), 0, 0.627, 2.0, None))
    assert line == (
        "thesis 2026-10-13: unverified writes 0 · AI authorship 63% · "
        "waste 2.0 per change · convergence unavailable"
    )
    assert week_label(date(2026, 10, 12)) == "2026-W42"
    assert ThesisMeasures.from_payload(_m().as_payload()) == _m()


def test_stored_unverified_keeps_every_breach_once_since_cutover() -> None:
    from shared.thesis_rules import stored_unverified

    a = {"sha": "a", "reason": "r", "first_seen": "2026-10-14"}
    records = [
        {"day": "2026-10-14", "unverified_breaches": [a]},
        {"day": "2026-10-15"},  # an older report without the field
        {
            "day": "2026-12-20",
            "unverified_breaches": [
                {**a, "first_seen": "2026-12-20"},
                {"sha": "b", "reason": "r", "first_seen": "2026-12-20"},
                {"sha": "c", "reason": "r", "first_seen": "2026-10-01"},
            ],
        },
    ]
    assert stored_unverified(records) == [
        a,
        {"sha": "b", "reason": "r", "first_seen": "2026-12-20"},
    ]


def test_a_corrected_breach_is_left_out_but_its_row_stays() -> None:
    from shared.thesis_rules import stored_unverified

    a = {
        "sha": "a",
        "reason": "PR #1: CI FAILURE on the merge commit",
        "first_seen": "2026-10-14",
    }
    b = {"sha": "b", "reason": "push by x", "first_seen": "2026-10-14"}
    records = [
        {"day": "2026-10-14", "unverified_breaches": [a, b]},
        {
            "day": "2026-10-15",
            "unverified_breaches": [b],
            "unverified_corrections": [{"sha": "a", "why_false": "cancelled"}],
        },
    ]
    assert stored_unverified(records) == [b]
    assert records[0]["unverified_breaches"] == [a, b]
