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
    deploy_trips,
    measure,
    merge_verdict,
    pr_trips,
    promotion_cutover,
    promotion_verdict,
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

    def __init__(
        self,
        writes: list[dict],
        prs: list[dict],
        pulls: dict[int, dict] | None = None,
        reviews: dict[int, list[dict]] | None = None,
    ) -> None:
        self.writes, self.prs = writes, prs
        self.pulls, self.reviews = pulls or {}, reviews or {}

    async def get_pages(self, path: str) -> list[dict]:
        if path.startswith("pulls/"):
            return self.reviews.get(int(path.split("/")[1]), [])
        return self.writes

    async def get_or_none(self, path: str) -> dict | None:
        return self.pulls.get(int(path.split("/")[1]))

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


def _checks(*runs: tuple[str, str | None], rollup: str = "FAILURE") -> dict:
    """A statusCheckRollup with its check runs as (status, conclusion)."""
    return {
        "state": rollup,
        "contexts": {
            "nodes": [
                {"__typename": "CheckRun", "status": st, "conclusion": co}
                for st, co in runs
            ]
        },
    }


def _merge_with(rollup: dict) -> dict:
    pr = _pr(same_tree=False)
    pr["mergeCommit"]["statusCheckRollup"] = rollup
    return pr


def test_a_cancelled_run_is_not_a_failure() -> None:
    """GitHub's combined state reads FAILURE when a newer merge cancels a
    main run (#1003, #1004 on 2026-10-14); only a completed red run fails."""
    cancelled = _checks(("COMPLETED", "SUCCESS"), ("COMPLETED", "CANCELLED"))
    assert merge_verdict(_merge_with(cancelled), GOV)[0] == "cancelled"
    red = _checks(("COMPLETED", "CANCELLED"), ("COMPLETED", "FAILURE"))
    assert merge_verdict(_merge_with(red), GOV)[0] == "unverified"
    running = _checks(("COMPLETED", "CANCELLED"), ("IN_PROGRESS", None))
    assert merge_verdict(_merge_with(running), GOV)[0] == "pending"
    skipped = _checks(("COMPLETED", "SUCCESS"), ("COMPLETED", "SKIPPED"))
    assert merge_verdict(_merge_with(skipped), GOV)[0] == "verified"


def _run(workflow: str, name: str, started: str, conclusion: str) -> dict:
    return {
        "__typename": "CheckRun",
        "name": name,
        "startedAt": started,
        "status": "COMPLETED",
        "conclusion": conclusion,
        "checkSuite": {"workflowRun": {"workflow": {"name": workflow}}},
    }


def _rollup(*runs: dict) -> dict:
    return {"state": "FAILURE", "contexts": {"nodes": list(runs)}}


def test_only_the_latest_run_of_a_check_counts() -> None:
    """#1072 and #1094 (2026-10-16): host-change-stated failed, the
    description was edited, and it passed on the same head before the merge.
    The superseded failure is not red CI; a failure after a pass still is,
    and a same-named job in another workflow is a different check."""
    fail = _run(
        "PR first line", "host-change-stated", "2026-10-16T05:57:45Z", "FAILURE"
    )
    ok = _run("PR first line", "host-change-stated", "2026-10-16T06:28:44Z", "SUCCESS")
    assert merge_verdict(_merge_with(_rollup(fail, ok)), GOV)[0] == "verified"
    assert merge_verdict(_merge_with(_rollup(ok, fail)), GOV)[0] == "verified"
    later_fail = {**fail, "startedAt": "2026-10-16T07:00:00Z"}
    assert merge_verdict(_merge_with(_rollup(ok, later_fail)), GOV)[0] == "unverified"
    other = _run("CI", "host-change-stated", "2026-10-16T05:00:00Z", "FAILURE")
    assert merge_verdict(_merge_with(_rollup(other, ok)), GOV)[0] == "unverified"


async def test_a_stored_false_ci_breach_gets_a_correction_row(tmp_path: Path) -> None:
    """A breach stored only because a cancelled run read as FAILURE is named
    false in a correction row and stops counting; the stored row is kept as
    it was. A breach stored for a missing approval is never corrected."""
    false = {
        "sha": MERGE,
        "reason": "PR #7: CI FAILURE on the merge commit",
        "first_seen": "2026-10-14",
    }
    push = {"sha": "p" * 40, "reason": "push by x", "first_seen": "2026-10-14"}
    cancelled = _merge_with(_checks(("COMPLETED", "CANCELLED")))
    writes = [
        {
            "activity_type": "pr_merge",
            "after": MERGE,
            "timestamp": "2026-10-14T04:00:00Z",
        }
    ]
    taken = await _measure(
        date(2026, 10, 15),
        _FakeGitHub(writes, [cancelled]),
        tmp_path,
        governor=GOV,
        stored=[false, push],
    )
    assert taken.measures.unverified_writes == 1
    assert taken.unverified_breaches == [push]
    [row] = taken.unverified_corrections
    assert row["sha"] == MERGE
    assert row["stored_reason"] == false["reason"]
    assert row["corrected_on"] == "2026-10-15"
    assert "cancelled" in row["why_false"]


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
                    "user",
                    ts,
                    "not set correctly: core-darek@core:/opt/dev/CORE$ core-admin daemon up\n"
                    "core-admin: command not found",
                ),
                _line(
                    "user",
                    ts,
                    [{"type": "text", "text": "<bash-input>ls</bash-input>"}],
                ),
                _line("user", ts, "A"),
                _line("user", ts, "mail me at a@b.com: thanks $ 5"),
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
        "command run by the governor": 2,
    }


def test_deploy_trips(tmp_path: Path) -> None:
    """2026-10-14: after a reboot the runner's deploy of 550969cf was
    refused (API down) and the governor redeployed it by hand. The runner's
    repeated "merged by" lines (waiting for CI) are not trips."""
    ledger = tmp_path / "deploy-ledger.jsonl"
    ledger.write_text(
        "\n".join(
            json.dumps(e)
            for e in [
                {
                    "action": "deploy",
                    "at": "2026-10-14T06:21:18+00:00",
                    "by": "core-runner",
                },
                {"action": "deploy", "at": "2026-10-14T20:30:00+00:00", "by": "darek"},
                {"action": "deploy", "at": "2026-09-01T00:00:00+00:00", "by": "darek"},
            ]
        )
        + "\nnot json\n"
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "550969cfce2e.log").write_text(
        "[2026-10-14T20:04:11.0+00:00] merged by bot on gov's approval of 5b\n"
        "[2026-10-14T20:06:44.2+00:00] merged by bot on gov's approval of 5b\n"
        "[2026-10-14T20:11:36.5+00:00] $ sudo -n /usr/local/sbin/core-deploy 5509 --migrate\n"
        "core-deploy: refused: API /health did not answer; switched back\n\n(exit 1)\n"
    )
    (logs / "1f7888969b48.log").write_text(
        "[2026-10-14T06:10:00.0+00:00] merged by bot on gov's approval of 1f\n"
        "[2026-10-14T06:12:00.0+00:00] $ sudo -n /usr/local/sbin/core-deploy 1f78 --migrate\n"
        "core-deploy: live\n(exit 0)\n"
        "[2026-10-14T06:13:00.0+00:00] $ sudo -n -u core /usr/local/sbin/core-sandbox-check\n"
        "failed\n(exit 2)\n"
        "[2026-10-14T06:14:00.0+00:00] $ sudo -n /usr/local/sbin/core-deploy 1f78 --rollback\n"
        "(exit 1)\n"
    )
    (logs / "old.log").write_text(
        "[2026-09-01T00:00:00+00:00] $ sudo -n /usr/local/sbin/core-deploy 0 --migrate\n(exit 1)\n"
    )
    assert deploy_trips(ledger, logs, date(2026, 10, 1)) == {
        "deploy run by hand": 1,
        "deploy refused": 1,
        "post-deploy check failed": 1,
    }


async def test_unreadable_deploy_records_leave_waste_unavailable(
    tmp_path: Path,
) -> None:
    taken = await measure(
        date(2026, 10, 15),
        _FakeGitHub([], []),
        _git(),
        "ref",
        tmp_path,
        deploys=(tmp_path / "missing.jsonl", tmp_path),
        with_convergence=False,
        governor=GOV,
    )
    assert taken.measures.waste_per_change is None
    assert any(u.startswith("deploy records") for u in taken.unavailable)


async def test_transcripts_behind_a_closed_directory_are_unavailable(
    tmp_path: Path,
) -> None:
    """The daemon's user may not enter the transcripts' parent directory:
    stat() then raises PermissionError. The day is still measured, with the
    transcripts listed as unavailable (2026-10-14: the sensor crashed)."""
    closed = tmp_path / "closed"
    (closed / "projects").mkdir(parents=True)
    closed.chmod(0)
    try:
        taken = await measure(
            date(2026, 10, 15),
            _FakeGitHub([], []),
            _git(),
            "ref",
            closed / "projects",
            with_convergence=False,
            governor=GOV,
        )
    finally:
        closed.chmod(0o700)
    assert taken.measures.waste_per_change is None
    assert any("claude code transcripts" in u for u in taken.unavailable)


# -- #1107: telemetry samples are not findings ---------------------------------


def test_telemetry_patterns_match_the_prefix_literally() -> None:
    import re

    from body.services.thesis.measure import _telemetry_patterns

    (pattern,) = _telemetry_patterns(("loop_hold.sample::",))
    assert pattern == "loop\\_hold.sample::%"

    def like(value: str, pat: str) -> bool:  # PostgreSQL LIKE, backslash escape
        rx = re.sub(
            r"\\(.)|(%)|(_)|(.)",
            lambda m: (
                re.escape(m.group(1))
                if m.group(1)
                else ".*"
                if m.group(2)
                else "."
                if m.group(3)
                else re.escape(m.group(4))
            ),
            pat,
        )
        return re.fullmatch(rx, value, re.S) is not None

    assert like("loop_hold.sample::DbSyncWorker", pattern)
    assert not like("loopXhold.sample::DbSyncWorker", pattern)  # _ is literal
    assert not like("audit.violation::loop_hold.sample::x", pattern)


async def test_convergence_leaves_telemetry_out_and_says_how_much(monkeypatch) -> None:
    from contextlib import asynccontextmanager

    from body.services import service_registry as registry_module
    from body.services.thesis import measure as measure_module

    calls: list[tuple[str, dict]] = []

    class _Result:
        def __init__(self, rows):
            self.rows = rows

        def one(self):
            return self.rows[0]

        def all(self):
            return self.rows

    class _Session:
        async def execute(self, statement, params=None):
            sql = str(statement)
            calls.append((sql, params or {}))
            if "FILTER" in sql:
                return _Result([(1917, 1459)])
            if "GROUP BY status" in sql:
                return _Result([("resolved", 1943)])
            return _Result([])

    @asynccontextmanager
    async def _session():
        yield _Session()

    monkeypatch.setattr(registry_module.ServiceRegistry, "session", _session)
    value, counts = await measure_module._convergence(date(2026, 10, 9))

    assert counts == {
        "created": 1917,
        "resolved": 1943,
        "abandoned": 0,
        "telemetry_excluded": 1459,
    }
    assert value == round(1943 / 1917, 3)
    created_sql, created_params = calls[1]
    closed_sql, closed_params = calls[2]
    assert (
        "NOT subject LIKE ANY" in created_sql and "NOT subject LIKE ANY" in closed_sql
    )
    assert created_params["t"] == ["loop\\_hold.sample::%"] == closed_params["t"]


# -- the promotion cutover (ADR-171) ---------------------------------------------

PROMOTED = "p" * 40


def _promotion(sha: str = PROMOTED, ref: str = "promote/next", **change) -> dict:
    return {
        "state": "open",
        "base": {"ref": "live"},
        "head": {"ref": ref, "sha": sha},
        **change,
    }


def _review(commit: str = PROMOTED, login: str = GOV, state: str = "APPROVED"):
    return {"user": {"login": login}, "state": state, "commit_id": commit}


def _ledger_file(tmp_path: Path, *entries: dict) -> Path:
    ledger = tmp_path / "deploy-ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return ledger


def test_the_cutover_is_the_first_deploy_recorded_with_a_promotion(
    tmp_path: Path,
) -> None:
    ledger = _ledger_file(
        tmp_path,
        {"action": "deploy", "at": "2026-10-18T07:50:00+00:00", "sha": "a" * 40},
        {"action": "deploy", "at": "2026-10-20T09:00:00+00:00", "promotion": 1200},
        {"action": "deploy", "at": "2026-10-22T09:00:00+00:00", "promotion": 1210},
    )
    assert promotion_cutover(ledger) == date(2026, 10, 20)
    assert promotion_cutover(_ledger_file(tmp_path, {"action": "deploy"})) is None


def test_promotion_verdict() -> None:
    entry = {"sha": PROMOTED, "promotion": 1200}
    assert promotion_verdict(entry, _promotion(), [_review()], GOV) is None
    merged = _promotion(state="closed", merged=True)
    assert promotion_verdict(entry, merged, [_review()], GOV) is None
    cases = [
        ({"sha": PROMOTED}, _promotion(), [_review()], "without a promotion"),
        (entry, None, [], "not found"),
        (entry, _promotion(base={"ref": "main"}), [_review()], "does not go into"),
        (
            entry,
            _promotion(ref="x"),
            [_review()],
            "promote/",
        ),
        (entry, _promotion(sha="o" * 40), [_review()], "head is"),
        (entry, _promotion(state="closed", merged=False), [_review()], "closed"),
        (entry, _promotion(), [], "did not approve"),
        (entry, _promotion(), [_review(login="bot")], "did not approve"),
        (entry, _promotion(), [_review(commit="o" * 40)], "did not approve"),
        (
            entry,
            _promotion(),
            [_review(), _review(state="DISMISSED")],
            "did not approve",
        ),
    ]
    for e, pull, reviews, why in cases:
        verdict = promotion_verdict(e, pull, reviews, GOV)
        assert verdict is not None and why in verdict, (why, verdict)


async def test_after_the_cutover_deploys_count_and_main_writes_do_not(
    tmp_path: Path,
) -> None:
    """From the first promoted deploy, a self-merged write to main is
    integration (ADR-171); a deploy without an approved promotion is the
    unverified write."""
    ledger = _ledger_file(
        tmp_path,
        {
            "action": "deploy",
            "at": "2026-10-20T09:00:00+00:00",
            "sha": PROMOTED,
            "promotion": 1200,
        },
        {"action": "deploy", "at": "2026-10-21T09:00:00+00:00", "sha": "q" * 40},
        {"action": "rollback", "at": "2026-10-21T10:00:00+00:00", "sha": PROMOTED},
    )
    writes = [
        {  # before the cutover, unapproved: still counted
            "activity_type": "push",
            "after": "b" * 40,
            "actor": {"login": "x"},
            "timestamp": "2026-10-19T12:00:00Z",
        },
        {  # after the cutover: main is integration
            "activity_type": "pr_merge",
            "after": MERGE,
            "timestamp": "2026-10-20T12:00:00Z",
        },
    ]
    gh = _FakeGitHub(
        writes,
        [_pr(merger="claude-bot", reviews=())],
        pulls={1200: _promotion()},
        reviews={1200: [_review()]},
    )
    taken = await _measure(
        date(2026, 10, 22), gh, tmp_path, governor=GOV, deploys=(ledger, tmp_path)
    )
    assert [b["sha"] for b in taken.unverified_breaches] == ["b" * 40, "q" * 40]
    assert (
        taken.unverified_breaches[1]["reason"] == "deploy: deployed without a promotion"
    )
    assert taken.detail["unverified"]["promotion_cutover"] == "2026-10-20"
    assert taken.detail["unverified"]["deploys_judged"] == 2


async def test_before_any_promoted_deploy_main_writes_count_as_before(
    tmp_path: Path,
) -> None:
    ledger = _ledger_file(
        tmp_path,
        {"action": "deploy", "at": "2026-10-18T07:50:00+00:00", "sha": "a" * 40},
    )
    writes = [
        {
            "activity_type": "pr_merge",
            "after": MERGE,
            "timestamp": "2026-10-18T12:00:00Z",
        }
    ]
    gh = _FakeGitHub(writes, [_pr(merger="claude-bot", reviews=())])
    taken = await _measure(
        date(2026, 10, 19), gh, tmp_path, governor=GOV, deploys=(ledger, tmp_path)
    )
    assert [b["sha"] for b in taken.unverified_breaches] == [MERGE]
    assert taken.detail["unverified"]["promotion_cutover"] is None
