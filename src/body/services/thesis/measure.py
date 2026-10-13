# src/body/services/thesis/measure.py
"""Take the four thesis measures for one day (read-only).

Windows: authorship, convergence and unverified writes look back 30 days
(unverified writes never before the one-path cutover, 2026-10-12); waste
looks back 14 days, as the 2026-10-13 baseline did. Sources: GitHub's
activity API and pull requests, git log of the merge branch, the blackboard
(read-only transaction) and Claude Code's transcripts for this project. A
source that cannot be read leaves its measure None and is named in
``unavailable``; it never counts as zero.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from body.services.thesis.github import GitHub, GitHubUnavailable
from shared.logger import getLogger
from shared.thesis_rules import CUTOVER, ThesisMeasures


logger = getLogger(__name__)

LONG_WINDOW = timedelta(days=30)
WASTE_WINDOW = timedelta(days=14)
GREEN = "SUCCESS"
AI_AUTHOR = re.compile(r"claude|^core:", re.IGNORECASE)
CI_FAILED = ("FAILURE", "TIMED_OUT", "STARTUP_FAILURE")

_MERGED_PRS = """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  pullRequests(states:MERGED,first:100,orderBy:{field:UPDATED_AT,direction:DESC}){
    nodes{number mergeCommit{oid}
      commits(last:1){nodes{commit{statusCheckRollup{state}}}}}}}}"""

_PR_TIMELINES = """query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  pullRequests(first:100,orderBy:{field:UPDATED_AT,direction:DESC}){
    nodes{state mergedAt closedAt updatedAt
      timelineItems(first:100,itemTypes:[PULL_REQUEST_REVIEW,REVIEW_DISMISSED_EVENT,
        PULL_REQUEST_COMMIT,HEAD_REF_FORCE_PUSHED_EVENT]){nodes{__typename
        ... on PullRequestReview{state submittedAt}
        ... on ReviewDismissedEvent{createdAt}
        ... on HeadRefForcePushedEvent{createdAt}
        ... on PullRequestCommit{commit{committedDate messageHeadline
          checkSuites(first:10){nodes{conclusion workflowRun{workflow{name}}}}}}}}}}}}"""


@dataclass
# ID: d9692b68-7894-4037-96dc-4d0802d868a3
class Measurement:
    """Today's measures with what each was counted from."""

    measures: ThesisMeasures
    detail: dict[str, Any] = field(default_factory=dict)
    unavailable: list[str] = field(default_factory=list)


def _iso(day: date) -> str:
    return f"{day.isoformat()}T00:00:00Z"


# ID: f85ea490-224c-44f6-9b7a-dd18494bf064
def count_unverified(
    writes: list[dict[str, Any]], rollups: dict[str, str | None]
) -> list[str]:
    """Writes to main that did not pass a CI-green pull request: every
    direct push, and every merge whose PR head's checks are not green."""
    bad: list[str] = []
    for write in writes:
        sha = str(write.get("after", ""))
        if write.get("activity_type") == "pr_merge":
            if rollups.get(sha) != GREEN:
                bad.append(f"merge {sha[:12]} (PR checks {rollups.get(sha)})")
        else:
            actor = (write.get("actor") or {}).get("login")
            bad.append(f"{write.get('activity_type')} {sha[:12]} by {actor}")
    return bad


# ID: 562ec047-1701-4c8e-9ebc-d175f6e9ee9b
def ai_share(rows: list[tuple[str, str]]) -> tuple[float | None, Counter]:
    """AI share of commits: the author or a Co-Authored-By names Claude or a
    core: flow. Dependabot counts as neither and stays in the total."""
    kinds: Counter = Counter()
    for author, coauthors in rows:
        if "dependabot" in author:
            kinds["bot"] += 1
        elif AI_AUTHOR.search(author) or AI_AUTHOR.search(coauthors):
            kinds["ai"] += 1
        else:
            kinds["human_or_unmarked"] += 1
    total = sum(kinds.values())
    return (round(kinds["ai"] / total, 3) if total else None), kinds


# ID: 416c79f6-e213-4ceb-b97d-f44f45b4afb4
def pr_trips(nodes: list[dict[str, Any]], since: date) -> Counter:
    """Pull-request round trips that did not move main: approvals dismissed,
    force-pushes, CI reruns after branch updates (and those after approval),
    commits after approval, red CI runs, PRs closed unmerged."""
    start = _iso(since)
    trips: Counter = Counter()
    for pr in nodes:
        if pr["updatedAt"] < start:
            continue
        items = pr["timelineItems"]["nodes"]
        approved = min(
            (i["submittedAt"] for i in items if i.get("state") == "APPROVED"),
            default=None,
        )
        for item in items:
            kind = item["__typename"]
            if kind == "ReviewDismissedEvent" and item["createdAt"] >= start:
                trips["approval dismissed"] += 1
            elif kind == "HeadRefForcePushedEvent" and item["createdAt"] >= start:
                trips["force-push"] += 1
            elif kind == "PullRequestCommit":
                trips.update(_commit_trips(item["commit"], approved, start))
        closed = pr.get("closedAt") or ""
        if pr["state"] == "CLOSED" and not pr.get("mergedAt") and closed >= start:
            trips["PR closed unmerged"] += 1
    return trips


def _commit_trips(commit: dict[str, Any], approved: str | None, start: str) -> Counter:
    trips: Counter = Counter()
    when = commit["committedDate"]
    if when < start:
        return trips
    after_approval = bool(approved and when > approved)
    if commit["messageHeadline"].startswith("Merge "):
        trips["CI rerun after branch update"] += 1
        if after_approval:
            trips["branch updated after approval"] += 1
    elif after_approval:
        trips["commit after approval"] += 1
    for suite in commit["checkSuites"]["nodes"]:
        workflow = ((suite.get("workflowRun") or {}).get("workflow") or {}).get(
            "name", ""
        )
        if workflow.lower().startswith("core") and suite["conclusion"] in CI_FAILED:
            trips["CI red"] += 1
    return trips


# ID: dfe65a20-41da-4eaa-a41b-561683cb7b99
def transcript_trips(root: Path, since: date) -> Counter:
    """Claude Code round trips in this project's transcripts: questions to
    the governor, permission blocks, commits refused by a hook, replies the
    stop hook sent back for being too long."""
    start = _iso(since)
    trips: Counter = Counter()
    for path in root.rglob("*.jsonl"):
        if date.fromtimestamp(os.path.getmtime(path)) < since:
            continue
        with path.open(errors="replace") as handle:
            for line in handle:
                trips.update(_event_trips(line, start))
    return trips


def _event_trips(line: str, start: str) -> Counter:
    trips: Counter = Counter()
    try:
        event = json.loads(line)
    except ValueError:
        return trips
    if (event.get("timestamp") or "") < start:
        return trips
    content = (event.get("message") or {}).get("content")
    if event.get("type") == "user":
        blob = json.dumps(content)
        if "Stop hook feedback" in blob and "lines outside code blocks" in blob:
            trips["stop-hook rewrite"] += 1
    if not isinstance(content, list):
        return trips
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use" and block.get("name") == "AskUserQuestion":
            trips["question to the governor"] += 1
        if block.get("type") != "tool_result":
            continue
        body = block.get("content")
        text = (
            body
            if isinstance(body, str)
            else " ".join(b.get("text", "") for b in body or [] if isinstance(b, dict))
        )
        if "Permission for this action was denied" in text:
            trips["permission block"] += 1
        if "hook error" in text and "commit refused" in text:
            trips["commit refused by a hook"] += 1
    return trips


async def _main_writes(gh: GitHub, since: date) -> list[dict[str, Any]]:
    writes = await gh.get_pages(
        "activity?ref=refs/heads/main&per_page=100&time_period=month"
    )
    return [w for w in writes if str(w.get("timestamp", "")) >= _iso(since)]


async def _merged_rollups(gh: GitHub) -> dict[str, str | None]:
    owner, name = gh.repo.split("/", 1)
    data = await gh.graphql(_MERGED_PRS, {"owner": owner, "name": name})
    rollups: dict[str, str | None] = {}
    for pr in data["repository"]["pullRequests"]["nodes"]:
        if pr.get("mergeCommit"):
            head = pr["commits"]["nodes"][0]["commit"].get("statusCheckRollup") or {}
            rollups[pr["mergeCommit"]["oid"]] = head.get("state")
    return rollups


async def _convergence(since: date) -> tuple[float | None, dict[str, int]]:
    from sqlalchemy import text

    from body.services.service_registry import ServiceRegistry

    start = datetime.combine(since, time(), tzinfo=UTC)
    async with ServiceRegistry.session() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        created = (
            await session.execute(
                text(
                    "SELECT count(*) FROM core.blackboard_entries "
                    "WHERE entry_type = 'finding' AND created_at >= :s"
                ),
                {"s": start},
            )
        ).scalar() or 0
        closed = dict(
            (
                await session.execute(
                    text(
                        "SELECT status, count(*) FROM core.blackboard_entries "
                        "WHERE entry_type = 'finding' AND updated_at >= :s "
                        "AND status IN ('resolved', 'abandoned') GROUP BY status"
                    ),
                    {"s": start},
                )
            ).all()
        )
    counts = {
        "created": int(created),
        "resolved": int(closed.get("resolved", 0)),
        "abandoned": int(closed.get("abandoned", 0)),
    }
    value = round(counts["resolved"] / counts["created"], 3) if created else None
    return value, counts


# ID: b5ac3580-864c-424e-bdd5-44ad4251555a
async def measure(
    day: date,
    gh: GitHub,
    git_service: Any,
    ref: str,
    transcripts: Path,
    *,
    with_convergence: bool = True,
) -> Measurement:
    """The four measures for *day*; each source is read independently."""
    long_since = day - LONG_WINDOW
    waste_since = day - WASTE_WINDOW
    detail: dict[str, Any] = {}
    unavailable: list[str] = []

    unverified: int | None = None
    writes_14: int | None = None
    try:
        writes = await _main_writes(gh, max(long_since, CUTOVER))
        bad = count_unverified(writes, await _merged_rollups(gh))
        unverified = len(bad)
        detail["unverified"] = {"writes": len(writes), "list": bad}
        writes_14 = len(await _main_writes(gh, waste_since))
    except GitHubUnavailable as exc:
        unavailable.append(f"github writes: {exc}")

    share: float | None = None
    try:
        share, kinds = ai_share(git_service.authors_since(ref, long_since.isoformat()))
        detail["authorship"] = dict(kinds)
    except Exception as exc:
        unavailable.append(f"git log {ref}: {exc}")

    converged: float | None = None
    if with_convergence:
        try:
            converged, counts = await _convergence(long_since)
            detail["convergence"] = counts
        except Exception as exc:
            unavailable.append(f"blackboard: {type(exc).__name__}: {exc}")

    waste: float | None = None
    trips: Counter = Counter()
    try:
        owner, name = gh.repo.split("/", 1)
        data = await gh.graphql(_PR_TIMELINES, {"owner": owner, "name": name})
        trips += pr_trips(data["repository"]["pullRequests"]["nodes"], waste_since)
    except GitHubUnavailable as exc:
        unavailable.append(f"github pull requests: {exc}")
        trips = Counter()
    readable = transcripts.is_dir() and os.access(transcripts, os.R_OK | os.X_OK)
    if not readable:
        unavailable.append(f"claude code transcripts: {transcripts} not readable")
    if readable and not any(u.startswith("github") for u in unavailable):
        trips += transcript_trips(transcripts, waste_since)
        if writes_14:
            waste = round(sum(trips.values()) / writes_14, 1)
    detail["waste"] = {"trips": dict(trips.most_common()), "writes": writes_14}

    if unavailable:
        logger.warning("thesis: unavailable sources: %s", "; ".join(unavailable))
    return Measurement(
        ThesisMeasures(day, unverified, share, waste, converged),
        detail,
        unavailable,
    )
