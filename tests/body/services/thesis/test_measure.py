"""Thesis measures: what counts as an unverified write, AI authorship and a
waste trip. These reproduce the 2026-10-13 baseline method."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from body.services.thesis.measure import (
    ai_share,
    count_unverified,
    measure,
    merge_verdict,
    pr_trips,
    transcript_trips,
)


GOV = "governor-login"
HEAD = "h" * 40
MERGE = "m" * 40


def _pr(
    merger: str = "claude-bot",
    reviews: tuple[tuple[str, str, str], ...] = ((GOV, "APPROVED", HEAD),),
    ci: str | None = "SUCCESS",
    merge_ci: str | None = None,
    same_tree: bool = True,
    number: int = 7,
) -> dict:
    """A merged pull request as _MERGED_PRS returns it."""
    return {
        "number": number,
        "updatedAt": "2026-10-14T12:00:00Z",
        "mergedBy": {"login": merger},
        "mergeCommit": {
            "oid": MERGE,
            "tree": {"oid": "t1" if same_tree else "t2"},
            "statusCheckRollup": {"state": merge_ci} if merge_ci else None,
        },
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": HEAD,
                        "tree": {"oid": "t1"},
                        "statusCheckRollup": {"state": ci} if ci else None,
                    }
                }
            ]
        },
        "reviews": {
            "nodes": [
                {"author": {"login": who}, "state": state, "commit": {"oid": oid}}
                for who, state, oid in reviews
            ]
        },
    }


def test_direct_pushes_and_red_merges_are_unverified() -> None:
    writes = [
        {"activity_type": "pr_merge", "after": "a" * 40},
        {"activity_type": "pr_merge", "after": "b" * 40},
        {"activity_type": "push", "after": "c" * 40, "actor": {"login": "x"}},
        {"activity_type": "pr_merge", "after": "d" * 40},
    ]
    prs = {"a" * 40: _pr(), "b" * 40: _pr(ci="FAILURE")}
    bad, pending = count_unverified(writes, prs, GOV)
    assert [b["sha"][0] for b in bad] == ["b", "c", "d"]
    assert bad[0]["reason"] == "PR #7: CI FAILURE on the PR head"
    assert bad[1]["reason"] == "push by x"
    assert bad[2]["reason"] == "merge with no pull request found"
    assert pending == []


def test_the_runner_criterion() -> None:
    # The governor merged it: verified without a review.
    assert merge_verdict(_pr(merger=GOV, reviews=()), GOV)[0] == "verified"
    # Someone else merged it after the governor approved the exact head.
    assert merge_verdict(_pr(), GOV)[0] == "verified"
    # Approval on an earlier commit, by another account, or withdrawn.
    for reviews in (
        ((GOV, "APPROVED", "e" * 40),),
        (("someone-else", "APPROVED", HEAD),),
        ((GOV, "APPROVED", HEAD), (GOV, "CHANGES_REQUESTED", HEAD)),
        ((GOV, "APPROVED", HEAD), (GOV, "DISMISSED", HEAD)),
    ):
        assert merge_verdict(_pr(reviews=reviews), GOV)[0] == "unverified"
    # A comment after the approval does not withdraw it.
    assert (
        merge_verdict(
            _pr(reviews=((GOV, "APPROVED", HEAD), (GOV, "COMMENTED", HEAD))), GOV
        )[0]
        == "verified"
    )
    # CI: the merge commit counts when the merge's tree differs from the head's.
    assert merge_verdict(_pr(same_tree=False, merge_ci="FAILURE"), GOV) == (
        "unverified",
        "CI FAILURE on the merge commit",
    )
    assert merge_verdict(_pr(same_tree=False, merge_ci="SUCCESS", ci=None), GOV)[0] == (
        "verified"
    )
    assert merge_verdict(_pr(ci="PENDING"), GOV)[0] == "pending"
    assert merge_verdict(_pr(ci=None), GOV)[0] == "unverified"


class _FakeGitHub:
    """GitHub as measure() reads it: main's writes and the merged PRs."""

    repo = "owner/name"

    def __init__(self, writes: list[dict], prs: list[dict]) -> None:
        self.writes, self.prs = writes, prs

    async def get_pages(self, path: str) -> list[dict]:
        return self.writes

    async def graphql(self, query: str, variables: dict) -> dict:
        if "mergeCommit" in query:
            return {
                "repository": {
                    "pullRequests": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": self.prs,
                    }
                }
            }
        return {"repository": {"pullRequests": {"nodes": []}}}


def _git() -> MagicMock:
    git = MagicMock()
    git.authors_since.return_value = []
    return git


async def _measure(day: date, gh: _FakeGitHub, tmp_path: Path, **kw):
    return await measure(day, gh, _git(), "ref", tmp_path, with_convergence=False, **kw)


async def test_ci_green_merge_without_the_governors_approval_is_unverified(
    tmp_path: Path,
) -> None:
    """CI green, merged by another account, the governor's approval was on an
    earlier commit: the runner would not deploy it, so it is unverified."""
    writes = [
        {
            "activity_type": "pr_merge",
            "after": MERGE,
            "timestamp": "2026-10-14T12:00:00Z",
        }
    ]
    stale = _pr(reviews=((GOV, "APPROVED", "e" * 40),))
    taken = await _measure(
        date(2026, 10, 15), _FakeGitHub(writes, [stale]), tmp_path, governor=GOV
    )
    assert taken.measures.unverified_writes == 1
    assert taken.unverified_breaches == [
        {
            "sha": MERGE,
            "reason": (
                f"PR #7: merged by claude-bot without {GOV}'s approval of its "
                f"last commit {HEAD[:12]}"
            ),
            "first_seen": "2026-10-15",
        }
    ]


async def test_a_stored_breach_counts_after_the_window(tmp_path: Path) -> None:
    """A breach first seen 2026-10-14 still counts on 2026-12-31, when the
    write has long left GitHub's month of activity; a new one is added."""
    old = {"sha": "o" * 40, "reason": "push by x", "first_seen": "2026-10-14"}
    writes = [
        {
            "activity_type": "push",
            "after": "n" * 40,
            "actor": {"login": "y"},
            "timestamp": "2026-12-30T12:00:00Z",
        }
    ]
    taken = await _measure(
        date(2026, 12, 31),
        _FakeGitHub(writes, []),
        tmp_path,
        governor=GOV,
        stored=[old],
    )
    assert taken.measures.unverified_writes == 2
    assert taken.unverified_breaches[0] == old
    assert taken.unverified_breaches[1]["first_seen"] == "2026-12-31"


async def test_without_the_governors_login_unverified_is_unavailable(
    tmp_path: Path,
) -> None:
    old = {"sha": "o" * 40, "reason": "push by x", "first_seen": "2026-10-14"}
    taken = await _measure(
        date(2026, 10, 15), _FakeGitHub([], []), tmp_path, stored=[old]
    )
    assert taken.measures.unverified_writes is None
    assert any("GOVERNOR_GITHUB" in u for u in taken.unavailable)
    assert taken.unverified_breaches == [old]  # kept, never dropped


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
