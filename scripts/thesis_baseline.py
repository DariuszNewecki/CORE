#!/usr/bin/env python3
"""scripts/thesis_baseline.py — the four thesis measures, rerunnable.

Read-only. Measures the thesis in .specs/DECISIONS.md ("Thesis and
baselines (2026-10-13)"):

  unverified   writes to main (GitHub activity API) that did not pass
               a PR with green CI: every direct push, and every PR merge
               whose head's check rollup is not SUCCESS. The custody
               ledger's entries are listed with their approvers.
  authorship   non-merge commits reaching main, AI when the author or a
               Co-Authored-By trailer names Claude or a core: flow.
  convergence  findings resolved (not abandoned) / findings created, from
               core.blackboard_entries (read-only transaction).
  waste        round trips that reached the governor or Claude Code
               without moving main (PR rework, CI reds and reruns, force
               pushes, unmerged PRs; Claude Code questions, permission
               blocks, stop-hook rewrites, refused commits), per write to
               main in the same window.

Needs: gh (authenticated), git, the CORE venv with PYTHONPATH=src and a
DATABASE_URL for the blackboard (run from the dev checkout, whose .env
carries it). A source that cannot be read is reported
as such, never as zero.

    cd /opt/dev/CORE && PYTHONPATH=src .venv/bin/python scripts/thesis_baseline.py
    ... --since 2026-09-13 --waste-since 2026-09-29 --json
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import glob
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path


REPO = "DariuszNewecki/CORE"
LEDGER = Path(os.environ.get("CORE_CUSTODY_LEDGER", "/opt/core/custody/ledger.jsonl"))
CLAUDE_LOGS = Path.home() / ".claude" / "projects" / "-opt-dev-CORE"
AI = re.compile(r"claude|^core:", re.IGNORECASE)


def _gh(*args: str) -> object:
    done = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    text = done.stdout.strip()
    # --paginate concatenates JSON arrays.
    return json.loads(text.replace("]\n[", ",").replace("][", ","))


def _iso(day: dt.date) -> str:
    return f"{day.isoformat()}T00:00:00Z"


def main_writes(since: dt.date) -> list[dict]:
    period = "month" if (dt.date.today() - since).days <= 31 else "quarter"
    rows = _gh(
        "api",
        "--paginate",
        f"repos/{REPO}/activity?ref=refs/heads/main&per_page=100&time_period={period}",
    )
    assert isinstance(rows, list)
    return [r for r in rows if r["timestamp"] >= _iso(since)]


def unverified(since: dt.date) -> dict:
    writes = main_writes(since)
    query = """query($n:Int!){repository(owner:"DariuszNewecki",name:"CORE"){
      pullRequests(states:MERGED,first:$n,orderBy:{field:UPDATED_AT,direction:DESC}){
        nodes{number mergeCommit{oid}
          commits(last:1){nodes{commit{statusCheckRollup{state}}}}}}}}"""
    data = _gh("api", "graphql", "-F", "n=100", "-f", f"query={query}")
    assert isinstance(data, dict)
    rollup = {}
    for pr in data["data"]["repository"]["pullRequests"]["nodes"]:
        if pr["mergeCommit"]:
            head = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"] or {}
            rollup[pr["mergeCommit"]["oid"]] = (pr["number"], head.get("state"))
    bad = []
    for w in writes:
        if w["activity_type"] == "pr_merge":
            number, state = rollup.get(w["after"], (None, None))
            if state != "SUCCESS":
                bad.append((w["timestamp"], "merge", f"#{number}", str(state)))
        else:
            bad.append(
                (
                    w["timestamp"],
                    w["activity_type"],
                    w["actor"]["login"],
                    w["after"][:8],
                )
            )
    ledger = []
    if LEDGER.is_file():
        for line in LEDGER.read_text().splitlines():
            entry = json.loads(line)
            if entry.get("approved_utc", "") >= _iso(since):
                ledger.append(entry.get("approver"))
    return {
        "writes": len(writes),
        "unverified": len(bad),
        "unverified_list": bad,
        "ledger_entries": len(ledger),
        "ledger_without_approver": sum(1 for a in ledger if not a),
    }


def authorship(since: dt.date) -> dict:
    out = subprocess.run(
        [
            "git",
            "log",
            "origin/main",
            "--no-merges",
            f"--since={since.isoformat()}",
            "--format=%an%x09%(trailers:key=Co-Authored-By,valueonly,separator=;)",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    kinds = Counter()
    for line in out.splitlines():
        author, _, coauthors = line.partition("\t")
        if "dependabot" in author:
            kinds["bot"] += 1
        elif AI.search(author) or AI.search(coauthors):
            kinds["ai"] += 1
        else:
            kinds["human_or_unmarked"] += 1
    total = sum(kinds.values())
    return {
        **kinds,
        "total": total,
        "ai_share": round(kinds["ai"] / total, 3) if total else None,
    }


async def _convergence(since: dt.datetime) -> dict:
    from sqlalchemy import text

    from shared.infrastructure.database.session_manager import get_session

    async with get_session() as s:
        await s.execute(text("SET TRANSACTION READ ONLY"))
        created = (
            await s.execute(
                text(
                    "select count(*) from core.blackboard_entries "
                    "where entry_type='finding' and created_at >= :s"
                ),
                {"s": since},
            )
        ).scalar()
        closed = dict(
            (
                await s.execute(
                    text(
                        "select status, count(*) from core.blackboard_entries "
                        "where entry_type='finding' and updated_at >= :s "
                        "and status in ('resolved','abandoned') group by 1"
                    ),
                    {"s": since},
                )
            ).all()
        )
    resolved = closed.get("resolved", 0)
    return {
        "created": created,
        "resolved": resolved,
        "abandoned": closed.get("abandoned", 0),
        "convergence": round(resolved / created, 3) if created else None,
    }


def convergence(since: dt.date) -> dict:
    start = dt.datetime.combine(since, dt.time(), tzinfo=dt.UTC)
    try:
        return asyncio.run(_convergence(start))
    except Exception as exc:
        return {"unreadable": f"{type(exc).__name__}: {exc}"}


def _github_trips(since: dt.date) -> Counter:
    query = """query($cursor:String){repository(owner:"DariuszNewecki",name:"CORE"){
      pullRequests(first:100,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}){
        nodes{state mergedAt closedAt updatedAt
          timelineItems(first:100,itemTypes:[PULL_REQUEST_REVIEW,REVIEW_DISMISSED_EVENT,
            PULL_REQUEST_COMMIT,HEAD_REF_FORCE_PUSHED_EVENT]){nodes{__typename
            ... on PullRequestReview{state submittedAt}
            ... on ReviewDismissedEvent{createdAt}
            ... on HeadRefForcePushedEvent{createdAt}
            ... on PullRequestCommit{commit{committedDate messageHeadline
              checkSuites(first:10){nodes{conclusion createdAt
                workflowRun{workflow{name}}}}}}}}}}}}"""
    data = _gh("api", "graphql", "-f", f"query={query}")
    assert isinstance(data, dict)
    start = _iso(since)
    trips = Counter()
    for pr in data["data"]["repository"]["pullRequests"]["nodes"]:
        if pr["updatedAt"] < start:
            continue
        items = pr["timelineItems"]["nodes"]
        approved = min(
            (i["submittedAt"] for i in items if i.get("state") == "APPROVED"),
            default=None,
        )
        for i in items:
            kind = i["__typename"]
            if kind == "ReviewDismissedEvent" and i["createdAt"] >= start:
                trips["approval dismissed"] += 1
            elif kind == "HeadRefForcePushedEvent" and i["createdAt"] >= start:
                trips["force-push"] += 1
            elif kind == "PullRequestCommit":
                c = i["commit"]
                if c["committedDate"] < start:
                    continue
                if c["messageHeadline"].startswith("Merge "):
                    trips["CI rerun after branch update"] += 1
                    if approved and c["committedDate"] > approved:
                        trips["branch updated after approval"] += 1
                elif approved and c["committedDate"] > approved:
                    trips["commit after approval"] += 1
                for suite in c["checkSuites"]["nodes"]:
                    name = ((suite.get("workflowRun") or {}).get("workflow") or {}).get(
                        "name", ""
                    )
                    if name.lower().startswith("core") and suite["conclusion"] in (
                        "FAILURE",
                        "TIMED_OUT",
                        "STARTUP_FAILURE",
                    ):
                        trips["CI red"] += 1
        if (
            pr["state"] == "CLOSED"
            and not pr["mergedAt"]
            and (pr["closedAt"] or "") >= start
        ):
            trips["PR closed unmerged"] += 1
    return trips


def _claude_trips(since: dt.date) -> Counter:
    start = _iso(since)
    trips = Counter()
    for path in glob.glob(str(CLAUDE_LOGS / "**" / "*.jsonl"), recursive=True):
        if dt.date.fromtimestamp(os.path.getmtime(path)) < since:
            continue
        with open(path, errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if (event.get("timestamp") or "") < start:
                    continue
                content = (event.get("message") or {}).get("content")
                if event.get("type") == "user":
                    blob = json.dumps(content)
                    if (
                        "Stop hook feedback" in blob
                        and "lines outside code blocks" in blob
                    ):
                        trips["stop-hook rewrite"] += 1
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if (
                        block.get("type") == "tool_use"
                        and block.get("name") == "AskUserQuestion"
                    ):
                        trips["question to the governor"] += 1
                    if block.get("type") != "tool_result":
                        continue
                    body = block.get("content")
                    text = (
                        body
                        if isinstance(body, str)
                        else " ".join(
                            b.get("text", "") for b in body or [] if isinstance(b, dict)
                        )
                    )
                    if "Permission for this action was denied" in text:
                        trips["permission block"] += 1
                    if "hook error" in text and "commit refused" in text:
                        trips["commit refused by a hook"] += 1
    return trips


def waste(since: dt.date) -> dict:
    out: dict = {"unreadable": []}
    trips = Counter()
    try:
        trips += _github_trips(since)
    except Exception as exc:
        out["unreadable"].append(f"github: {exc}")
    if CLAUDE_LOGS.is_dir():
        trips += _claude_trips(since)
    else:
        out["unreadable"].append(f"claude code logs: {CLAUDE_LOGS} missing")
    writes = len(main_writes(since))
    total = sum(trips.values())
    out.update(
        trips=dict(trips.most_common()),
        total=total,
        merged_changes=writes,
        per_merged_change=round(total / writes, 1) if writes else None,
    )
    return out


def main() -> None:
    today = dt.date.today()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--since", type=dt.date.fromisoformat, default=today - dt.timedelta(30)
    )
    parser.add_argument(
        "--waste-since", type=dt.date.fromisoformat, default=today - dt.timedelta(14)
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = {
        "since": args.since.isoformat(),
        "unverified_writes": unverified(args.since),
        "authorship": authorship(args.since),
        "convergence": convergence(args.since),
        "waste": {"since": args.waste_since.isoformat(), **waste(args.waste_since)},
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return
    u, a, c, w = (
        result["unverified_writes"],
        result["authorship"],
        result["convergence"],
        result["waste"],
    )
    print(f"since {result['since']}")
    print(
        f"unverified writes to main: {u['unverified']} of {u['writes']}"
        f" (ledger: {u['ledger_entries']}, {u['ledger_without_approver']} without approver)"
    )
    print(f"AI authorship: {a['ai_share']} ({a.get('ai', 0)} of {a['total']})")
    print(
        f"convergence: {c.get('convergence', c.get('unreadable'))}"
        f" ({c.get('resolved')} resolved, {c.get('abandoned')} abandoned, {c.get('created')} created)"
    )
    print(
        f"waste since {w['since']}: {w['per_merged_change']} per merged change"
        f" ({w['total']} trips / {w['merged_changes']} writes); unreadable: {w['unreadable'] or 'none'}"
    )


if __name__ == "__main__":
    main()
