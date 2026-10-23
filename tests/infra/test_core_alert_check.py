"""core_alert_check.py: one issue per pipeline problem (review finding F4)."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path


_PATH = Path(__file__).resolve().parents[2] / "infra/scripts/core_alert_check.py"
_SPEC = importlib.util.spec_from_file_location("core_alert_check", _PATH)
assert _SPEC and _SPEC.loader
ac = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ac)

NOW = dt.datetime(2026, 10, 23, 12, 0, tzinfo=dt.UTC)
SHA = "a" * 40


def _status(**fields) -> dict:
    return {
        "at": (NOW - dt.timedelta(minutes=2)).isoformat(),
        "state": "idle",
        **fields,
    }


def test_a_healthy_pipeline_has_no_problem() -> None:
    assert ac.problems(_status(last={"result": "live", "sha": SHA}), NOW) == {}


def test_each_failure_is_its_own_problem() -> None:
    found = ac.problems(
        _status(
            state="error",
            error="HTTP 403",
            last={
                "result": "failed",
                "sha": SHA,
                "promotion": 1254,
                "what": "CI is red",
            },
        ),
        NOW,
    )
    assert set(found) == {"pipeline-error", f"promotion-failed-{SHA[:12]}"}
    assert "HTTP 403" in found["pipeline-error"]
    assert "#1254" in found[f"promotion-failed-{SHA[:12]}"]


def test_a_status_not_written_for_15_minutes_is_a_stall() -> None:
    old = _status(at=(NOW - dt.timedelta(minutes=16)).isoformat())
    assert set(ac.problems(old, NOW)) == {"pipeline-stalled"}
    assert set(ac.problems(None, NOW)) == {"pipeline-stalled"}
    assert set(ac.problems(_status(at="garbage"), NOW)) == {"pipeline-stalled"}


class _Gh:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        return ""


def test_a_new_problem_opens_one_issue_that_mentions_the_governor() -> None:
    gh = _Gh()
    done = ac.reconcile({"pipeline-error": "it failed"}, {}, gh)
    assert done == ["opened pipeline-error"]
    (call,) = gh.calls
    assert call[:2] == ("issue", "create")
    assert call[call.index("--title") + 1].startswith("[alert] pipeline-error: ")
    assert call[call.index("--body") + 1].startswith(f"@{ac.GOVERNOR} ")


def test_an_open_problem_is_not_raised_again() -> None:
    # The dedupe: every 15 minutes, the same problem, still one issue.
    gh = _Gh()
    assert (
        ac.reconcile({"pipeline-error": "it failed"}, {"pipeline-error": 7}, gh) == []
    )
    assert gh.calls == []


def test_a_cleared_problem_closes_its_issue() -> None:
    gh = _Gh()
    assert ac.reconcile({}, {"pipeline-stalled": 9}, gh) == [
        "closed pipeline-stalled (#9)"
    ]
    assert gh.calls[0][:3] == ("issue", "close", "9")
