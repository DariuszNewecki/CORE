"""Thesis measures: what counts as an unverified write, AI authorship and a
waste trip. These reproduce the 2026-10-13 baseline method."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from body.services.thesis.measure import (
    ai_share,
    count_unverified,
    pr_trips,
    transcript_trips,
)


def test_direct_pushes_and_red_merges_are_unverified() -> None:
    writes = [
        {"activity_type": "pr_merge", "after": "a" * 40},
        {"activity_type": "pr_merge", "after": "b" * 40},
        {"activity_type": "push", "after": "c" * 40, "actor": {"login": "x"}},
    ]
    bad = count_unverified(writes, {"a" * 40: "SUCCESS", "b" * 40: "FAILURE"})
    assert len(bad) == 2
    assert bad[0].startswith("merge bbbbbbbbbbbb")
    assert bad[1] == "push cccccccccccc by x"


def test_ai_share_counts_authors_and_co_authors() -> None:
    share, kinds = ai_share(
        [
            ("Claude (CORE agent)", ""),
            ("Dariusz Newecki", "Claude Opus 5.5 <noreply@anthropic.com>"),
            ("core:flow.build_test_for_symbol", ""),
            ("Dariusz Newecki", ""),
            ("dependabot[bot]", ""),
        ]
    )
    assert kinds == {"ai": 3, "human_or_unmarked": 1, "bot": 1}
    assert share == 0.6
    assert ai_share([]) == (None, {})


def _commit(when: str, headline: str, ci: str | None = None) -> dict:
    suites = (
        [{"conclusion": ci, "workflowRun": {"workflow": {"name": "core-ci"}}}]
        if ci
        else []
    )
    return {
        "__typename": "PullRequestCommit",
        "commit": {
            "committedDate": when,
            "messageHeadline": headline,
            "checkSuites": {"nodes": suites},
        },
    }


def test_pr_trips() -> None:
    pr = {
        "state": "MERGED",
        "mergedAt": "2026-10-10T12:00:00Z",
        "closedAt": "2026-10-10T12:00:00Z",
        "updatedAt": "2026-10-10T12:00:00Z",
        "timelineItems": {
            "nodes": [
                _commit("2026-10-10T08:00:00Z", "fix: x", ci="FAILURE"),
                {
                    "__typename": "PullRequestReview",
                    "state": "APPROVED",
                    "submittedAt": "2026-10-10T09:00:00Z",
                },
                _commit("2026-10-10T10:00:00Z", "Merge branch 'main' into x"),
                _commit("2026-10-10T11:00:00Z", "fix: y"),
                {
                    "__typename": "HeadRefForcePushedEvent",
                    "createdAt": "2026-10-10T11:30:00Z",
                },
            ]
        },
    }
    closed = {**pr, "state": "CLOSED", "mergedAt": None, "timelineItems": {"nodes": []}}
    old = {**pr, "updatedAt": "2026-09-01T00:00:00Z"}
    trips = pr_trips([pr, closed, old], date(2026, 10, 1))
    assert trips == {
        "CI red": 1,
        "CI rerun after branch update": 1,
        "branch updated after approval": 1,
        "commit after approval": 1,
        "force-push": 1,
        "PR closed unmerged": 1,
    }


def _line(kind: str, ts: str, content) -> str:
    return json.dumps({"type": kind, "timestamp": ts, "message": {"content": content}})


def test_transcript_trips(tmp_path: Path) -> None:
    ts = "2026-10-12T10:00:00Z"
    (tmp_path / "s.jsonl").write_text(
        "\n".join(
            [
                _line(
                    "assistant", ts, [{"type": "tool_use", "name": "AskUserQuestion"}]
                ),
                _line(
                    "user",
                    ts,
                    [
                        {
                            "type": "tool_result",
                            "content": "Permission for this action was denied by the classifier",
                        }
                    ],
                ),
                _line(
                    "user",
                    ts,
                    [
                        {
                            "type": "tool_result",
                            "content": [
                                {"text": "PreToolUse:Bash hook error: commit refused"}
                            ],
                        }
                    ],
                ),
                _line("user", ts, "Stop hook feedback: 8 lines outside code blocks"),
                _line(
                    "assistant",
                    "2026-09-01T00:00:00Z",
                    [{"type": "tool_use", "name": "AskUserQuestion"}],
                ),
                "not json",
            ]
        )
    )
    assert transcript_trips(tmp_path, date(2026, 10, 1)) == {
        "question to the governor": 1,
        "permission block": 1,
        "commit refused by a hook": 1,
        "stop-hook rewrite": 1,
    }
