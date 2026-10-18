# src/body/services/thesis/measure.py
"""Take the four thesis measures for one day (read-only).

Windows: authorship and convergence look back 30 days; waste looks back 14
days, as the 2026-10-13 baseline did. Unverified writes are found in
GitHub's last month of writes to main and added to the ones already stored
(every breach since the one-path cutover, 2026-10-12, is kept for good and
never leaves the count). A write is verified only on the runner's criterion
(infra/core-pipeline): a pull request merged by the governor's GitHub
account, or whose exact last commit that account approved, with green CI.
From the first deploy recorded with its promotion (ADR-171, the promotion
cutover) main is integration: its writes are no longer counted, and the
writes that count are the deploys, each verified only when it records a
promotion into ``live`` whose head is the deployed commit and whose exact
head the governor approved. Sources: GitHub's
activity API and pull requests, git log of the merge branch, the blackboard
(read-only transaction), Claude Code's transcripts for this project, and the
deploy ledger with the post-merge runner's logs. A
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
RUNNER = "core-runner"
LIVE_BRANCH = "live"
SHELL_PROMPT = re.compile(r"(?:^|\s)[\w.-]+@[\w.-]+:[^\s$#]*[$#] \S")
RUNNER_ENTRY = re.compile(r"^\[([^\]]+)\] (.*?)(?=^\[[^\]]+\] |\Z)", re.M | re.S)
EXIT_LINE = re.compile(r"^\(exit (-?\d+)\)$", re.MULTILINE)
CI_FAILED = ("FAILURE", "TIMED_OUT", "STARTUP_FAILURE")
CI_PENDING = ("PENDING", "EXPECTED")
CI_RED = ("FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED")

# Every field the runner (infra/core-pipeline, Runner.merge/approved/ci)
# decides on: who merged, the governor's reviews and the commit each was on,
# the PR head and the merge commit with their trees and checks.
_MERGED_PRS = """query($owner:String!,$name:String!,$after:String){
  repository(owner:$owner,name:$name){
  pullRequests(states:MERGED,first:50,after:$after,
    orderBy:{field:UPDATED_AT,direction:DESC}){
    pageInfo{hasNextPage endCursor}
    nodes{number updatedAt mergedBy{login}
      mergeCommit{oid tree{oid} statusCheckRollup{state contexts(first:100){nodes{__typename
        ... on CheckRun{name startedAt status conclusion checkSuite{workflowRun{workflow{name}}}}
        ... on StatusContext{state}}}}}
      commits(last:1){nodes{commit{oid tree{oid} statusCheckRollup{state contexts(first:100){nodes{__typename
        ... on CheckRun{name startedAt status conclusion checkSuite{workflowRun{workflow{name}}}}
        ... on StatusContext{state}}}}}}}
      reviews(last:100){nodes{author{login} state commit{oid}}}}}}}"""

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
    unverified_breaches: list[dict[str, Any]] = field(default_factory=list)
    unverified_corrections: list[dict[str, Any]] = field(default_factory=list)


def _iso(day: date) -> str:
    return f"{day.isoformat()}T00:00:00Z"


# ID: 4d2f1734-520b-472f-b407-0e8ff817e1da
def governor_approved(reviews: list[dict[str, Any]], governor: str, head: str) -> bool:
    """The runner's ``approved``: the governor's account approved *head*, the
    pull request's exact last commit, and did not ask for changes after.
    Reviews are chronological; any other account's review never counts."""
    verdict = None
    for review in reviews:
        if (review.get("author") or {}).get("login") != governor:
            continue
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            verdict = (review.get("state"), (review.get("commit") or {}).get("oid"))
    return verdict == ("APPROVED", head)


def _latest_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The latest run of each check (workflow and job name); a run without a
    name is kept as it is."""
    latest: dict[Any, dict[str, Any]] = {}
    for index, run in enumerate(runs):
        name = run.get("name")
        suite = (run.get("checkSuite") or {}).get("workflowRun") or {}
        key = ((suite.get("workflow") or {}).get("name"), name) if name else index
        kept = latest.get(key)
        if kept is None or str(run.get("startedAt") or "") >= str(
            kept.get("startedAt") or ""
        ):
            latest[key] = run
    return list(latest.values())


# ID: 3c0f6a1e-7d42-4b9a-a8c5-1f2e9d6b4a70
def ci_state(commit: dict[str, Any] | None) -> str | None:
    """CI on *commit*: SUCCESS, PENDING, FAILURE, CANCELLED or None (no checks).

    Only a completed red run is a failure (governor 2026-10-14). GitHub's
    combined state reads FAILURE for a run cancelled when a newer merge
    superseded it, so the individual checks decide: any completed red one is
    FAILURE; else any still running is PENDING; else any cancelled is
    CANCELLED, which is not a failure; else SUCCESS.

    A check run again on the same commit (a pull request's description
    edited, #1066, #1072, #1094) counts only by its latest run, as GitHub's
    required checks and the runner's check-runs query (latest by default) do."""
    rollup = (commit or {}).get("statusCheckRollup") or {}
    state = rollup.get("state")
    if state == GREEN:
        return GREEN
    nodes = (rollup.get("contexts") or {}).get("nodes") or []
    if not nodes:
        return state
    runs = _latest_runs([n for n in nodes if n.get("__typename") == "CheckRun"])
    statuses = [n.get("state") for n in nodes if n.get("__typename") == "StatusContext"]
    done = [r for r in runs if r.get("status") == "COMPLETED"]
    if any(r.get("conclusion") in CI_RED for r in done) or any(
        s in ("FAILURE", "ERROR") for s in statuses
    ):
        return "FAILURE"
    if len(done) < len(runs) or any(s in CI_PENDING for s in statuses):
        return "PENDING"
    if any(r.get("conclusion") == "CANCELLED" for r in done):
        return "CANCELLED"
    return GREEN


# ID: 085b7f10-5c21-4be0-a297-1e165f7eb479
def merge_verdict(pr: dict[str, Any], governor: str) -> tuple[str, str]:
    """('verified' | 'pending' | 'cancelled' | 'unverified', why) for a merged
    pull request,
    on the runner's criterion: merged by the governor, or by anyone after the
    governor approved its exact last commit; then CI green on the PR head when
    the merge has the head's exact tree, else on the merge commit itself."""
    merger = (pr.get("mergedBy") or {}).get("login")
    heads = (pr.get("commits") or {}).get("nodes") or []
    head = heads[-1]["commit"] if heads else {}
    head_oid = head.get("oid")
    reviews = (pr.get("reviews") or {}).get("nodes") or []
    if merger != governor and not (
        head_oid and governor_approved(reviews, governor, head_oid)
    ):
        return "unverified", (
            f"merged by {merger} without {governor}'s approval of its last "
            f"commit {str(head_oid)[:12]}"
        )
    merge = pr.get("mergeCommit") or {}
    same_tree = (merge.get("tree") or {}).get("oid") == (head.get("tree") or {}).get(
        "oid"
    )
    state = ci_state(head) if same_tree else ci_state(merge)
    where = "PR head" if same_tree else "merge commit"
    if state == GREEN:
        return "verified", f"CI green on the {where}"
    if state in CI_PENDING:
        return "pending", f"CI {state} on the {where}"
    if state == "CANCELLED":
        return "cancelled", f"CI cancelled on the {where}, not a failure"
    return "unverified", f"CI {state} on the {where}"


# ID: f85ea490-224c-44f6-9b7a-dd18494bf064
def count_unverified(
    writes: list[dict[str, Any]], prs: dict[str, dict[str, Any]], governor: str
) -> tuple[list[dict[str, str]], list[str]]:
    """(unverified writes as {sha, reason}, merges whose CI is still running).

    Every direct push is unverified; a merge is judged by ``merge_verdict``
    on its pull request (*prs* by merge-commit sha), and a merge with no
    pull request found is unverified."""
    bad: list[dict[str, str]] = []
    pending: list[str] = []
    for write in writes:
        sha = str(write.get("after", ""))
        if write.get("activity_type") != "pr_merge":
            actor = (write.get("actor") or {}).get("login")
            bad.append(
                {"sha": sha, "reason": f"{write.get('activity_type')} by {actor}"}
            )
            continue
        pr = prs.get(sha)
        if pr is None:
            bad.append({"sha": sha, "reason": "merge with no pull request found"})
            continue
        verdict, why = merge_verdict(pr, governor)
        if verdict == "unverified":
            bad.append({"sha": sha, "reason": f"PR #{pr.get('number')}: {why}"})
        elif verdict == "pending":
            pending.append(sha)
    return bad, pending


# ID: 8b5e2d97-41c6-4f0a-9e3d-6a7c1b2f8e54
def false_ci_breaches(
    stored: list[dict[str, Any]],
    prs: dict[str, dict[str, Any]],
    governor: str,
    day: date,
) -> list[dict[str, Any]]:
    """Stored breaches that were false: kept only because CI was read as red,
    and that ``merge_verdict`` no longer judges unverified (a run cancelled
    when a newer merge superseded it, read as FAILURE before 2026-10-14; a
    failed run that a later run of the same check replaced, before 2026-10-17).

    The stored rows are never changed or deleted; each false one gets a
    correction row naming it and why. A breach kept for any other reason
    (a direct push, a missing approval) is never corrected here."""
    corrections: list[dict[str, Any]] = []
    for breach in stored:
        pr = prs.get(str(breach.get("sha", "")))
        if pr is None or ": CI " not in str(breach.get("reason", "")):
            continue
        verdict, why = merge_verdict(pr, governor)
        if verdict == "unverified":
            continue
        corrections.append(
            {
                "sha": breach["sha"],
                "stored_reason": breach.get("reason"),
                "first_seen": breach.get("first_seen"),
                "why_false": (
                    f"now judged {verdict} ({why}): only a completed red CI run "
                    "is a failure; a run cancelled by a newer merge is not "
                    "(governor 2026-10-14), nor one a later run of the same "
                    "check replaced"
                ),
                "corrected_on": day.isoformat(),
            }
        )
    return corrections


def _ledger(path: Path) -> list[dict[str, Any]]:
    entries = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


# ID: 8d2b25a4-5ddc-4979-9c89-49c6e7edb7bf
def promotion_cutover(ledger: Path) -> date | None:
    """The day of the first deploy recorded with its promotion (ADR-171);
    None before any. Raises OSError when the ledger cannot be read."""
    days = [
        str(e.get("at", ""))[:10]
        for e in _ledger(ledger)
        if e.get("action") == "deploy" and e.get("promotion") is not None
    ]
    return date.fromisoformat(min(days)) if days else None


# ID: 995031bf-2a16-4413-9f73-875936d1cc07
def promotion_verdict(
    entry: dict[str, Any],
    pull: dict[str, Any] | None,
    reviews: list[dict[str, Any]],
    governor: str,
) -> str | None:
    """Why the deploy *entry* is unverified, or None when it ran an approved
    promotion: a pull request into ``live`` from a ``promote/`` branch whose
    head is the deployed commit and whose exact head the governor approved
    (core-deploy's own check). *pull* and *reviews* are GitHub's REST answers."""
    sha = str(entry.get("sha", ""))
    number = entry.get("promotion")
    if number is None:
        return "deployed without a promotion"
    if pull is None:
        return f"promotion #{number} not found"
    head = pull.get("head") or {}
    if (pull.get("base") or {}).get("ref") != LIVE_BRANCH:
        return f"promotion #{number} does not go into {LIVE_BRANCH}"
    if not str(head.get("ref") or "").startswith("promote/"):
        return f"promotion #{number} is not from a promote/ branch"
    if head.get("sha") != sha:
        return f"promotion #{number}'s head is {str(head.get('sha'))[:12]}"
    if pull.get("state") != "open" and not pull.get("merged"):
        return f"promotion #{number} was closed without being merged"
    verdict = None
    for review in reviews:  # chronological
        if (review.get("user") or {}).get("login") != governor:
            continue
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            verdict = (review.get("state"), review.get("commit_id"))
    if verdict != ("APPROVED", sha):
        return f"promotion #{number}: {governor} did not approve {sha[:12]}"
    return None


# ID: 83f31623-af9a-4786-956d-7323e152cd07
async def unverified_deploys(
    gh: GitHub, ledger: Path, since: date, governor: str
) -> tuple[list[dict[str, str]], int]:
    """(deploys since *since* that ran no approved promotion, as {sha,
    reason}; how many deploys were judged). A rollback deploys nothing new
    and is not judged."""
    bad: list[dict[str, str]] = []
    deploys = [
        e
        for e in _ledger(ledger)
        if e.get("action") == "deploy" and str(e.get("at", "")) >= _iso(since)
    ]
    for entry in deploys:
        number = entry.get("promotion")
        pull, reviews = None, []
        if number is not None:
            pull = await gh.get_or_none(f"pulls/{int(number)}")
            if pull is not None:
                reviews = await gh.get_pages(
                    f"pulls/{int(number)}/reviews?per_page=100"
                )
        why = promotion_verdict(entry, pull, reviews, governor)
        if why:
            bad.append({"sha": str(entry.get("sha", "")), "reason": f"deploy: {why}"})
    return bad, len(deploys)


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
    stop hook sent back for being too long, and commands the governor ran by
    hand (a ``!`` command, or terminal output pasted with its prompt)."""
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
        typed = _typed_text(content)
        if "<bash-input>" in typed or SHELL_PROMPT.search(typed):
            trips["command run by the governor"] += 1
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


def _typed_text(content: Any) -> str:
    """What the governor typed or pasted; tool results are not typed."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    blocks = [b for b in content if isinstance(b, dict)]
    if any(b.get("type") == "tool_result" for b in blocks):
        return ""
    return " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")


# ID: be158f5c-054d-4ac0-bc27-ff654175eee8
def deploy_trips(ledger: Path, logs: Path, since: date) -> Counter:
    """Deploy round trips: deploys the governor ran by hand (deploy-ledger
    lines not written by the runner), and the runner's deploys that did not
    go live (core-deploy or its post-deploy check exited non-zero)."""
    start = _iso(since)
    trips: Counter = Counter()
    for line in ledger.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if str(entry.get("at", "")) >= start and entry.get("by") != RUNNER:
            trips["deploy run by hand"] += 1
    for path in sorted(logs.glob("*.log")):
        trips.update(_runner_log_trips(path.read_text(errors="replace"), start))
    return trips


def _runner_log_trips(text: str, start: str) -> Counter:
    trips: Counter = Counter()
    entries = [m.groups() for m in RUNNER_ENTRY.finditer(text)]
    for at, body in entries:
        if at.replace("+00:00", "Z") < start:
            continue
        first = body.split("\n", 1)[0]
        exit_code = EXIT_LINE.search(body)
        failed = exit_code is not None and exit_code.group(1) != "0"
        if "core-deploy" in first and "--rollback" not in first and failed:
            trips["deploy refused"] += 1
        elif "core-sandbox-check" in first and failed:
            trips["post-deploy check failed"] += 1
    return trips


async def _main_writes(gh: GitHub, since: date) -> list[dict[str, Any]]:
    writes = await gh.get_pages(
        "activity?ref=refs/heads/main&per_page=100&time_period=month"
    )
    return [w for w in writes if str(w.get("timestamp", "")) >= _iso(since)]


async def _merged_prs(gh: GitHub, since: date) -> dict[str, dict[str, Any]]:
    """Merged pull requests by merge-commit sha, every page updated since *since*."""
    owner, name = gh.repo.split("/", 1)
    prs: dict[str, dict[str, Any]] = {}
    after: str | None = None
    while True:
        data = await gh.graphql(
            _MERGED_PRS, {"owner": owner, "name": name, "after": after}
        )
        page = data["repository"]["pullRequests"]
        for pr in page["nodes"]:
            if pr.get("mergeCommit"):
                prs[pr["mergeCommit"]["oid"]] = pr
        nodes = page["nodes"]
        info = page.get("pageInfo") or {}
        if (
            not info.get("hasNextPage")
            or not nodes
            or str(nodes[-1].get("updatedAt", "")) < _iso(since)
        ):
            return prs
        after = info.get("endCursor")


def _telemetry_patterns(prefixes: tuple[str, ...]) -> list[str]:
    """LIKE patterns for subjects that begin with one of *prefixes*: telemetry
    samples, not findings (#1107). ``_``, ``%`` and ``\\`` are escaped."""
    return [
        p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        for p in prefixes
    ]


async def _convergence(since: date) -> tuple[float | None, dict[str, int]]:
    """Resolved / created findings since *since*. Telemetry samples
    (``blackboard.telemetry_subject_prefixes``, e.g. ``loop_hold.sample::``)
    are left out on both sides: they are never resolved, only expire, so
    counting them reads as findings abandoned (#1107). How many were left
    out is reported as ``telemetry_excluded``."""
    from sqlalchemy import text

    from body.services.service_registry import ServiceRegistry
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )

    patterns = _telemetry_patterns(
        tuple(load_operational_config().blackboard.telemetry_subject_prefixes)
    )
    telemetry = "subject LIKE ANY(CAST(:t AS text[]))"
    start = datetime.combine(since, time(), tzinfo=UTC)
    params = {"s": start, "t": patterns}
    async with ServiceRegistry.session() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        created, excluded = (
            await session.execute(
                text(
                    f"SELECT count(*) FILTER (WHERE NOT {telemetry}), "
                    f"count(*) FILTER (WHERE {telemetry}) "
                    "FROM core.blackboard_entries "
                    "WHERE entry_type = 'finding' AND created_at >= :s"
                ),
                params,
            )
        ).one()
        closed = dict(
            (
                await session.execute(
                    text(
                        "SELECT status, count(*) FROM core.blackboard_entries "
                        "WHERE entry_type = 'finding' AND updated_at >= :s "
                        "AND status IN ('resolved', 'abandoned') "
                        f"AND NOT {telemetry} GROUP BY status"
                    ),
                    params,
                )
            ).all()
        )
    created = int(created or 0)
    counts = {
        "created": created,
        "resolved": int(closed.get("resolved", 0)),
        "abandoned": int(closed.get("abandoned", 0)),
        "telemetry_excluded": int(excluded or 0),
    }
    value = round(counts["resolved"] / created, 3) if created else None
    return value, counts


# ID: b5ac3580-864c-424e-bdd5-44ad4251555a
async def measure(
    day: date,
    gh: GitHub,
    git_service: Any,
    ref: str,
    transcripts: Path,
    *,
    deploys: tuple[Path, Path] | None = None,
    with_convergence: bool = True,
    governor: str | None = None,
    stored: list[dict[str, Any]] | None = None,
) -> Measurement:
    """The four measures for *day*; each source is read independently.

    *deploys* is (deploy ledger, runner logs directory); when given, its
    trips count toward waste and an unreadable one leaves waste unavailable.
    *governor* is the governor's GitHub login (the runner's GOVERNOR_GITHUB);
    without it unverified writes cannot be judged and read as unavailable.
    *stored* are the unverified writes already kept (``stored_unverified``);
    they always count, and the result carries them plus today's new ones.
    """
    long_since = day - LONG_WINDOW
    waste_since = day - WASTE_WINDOW
    detail: dict[str, Any] = {}
    unavailable: list[str] = []
    kept = list(stored or [])
    corrections: list[dict[str, Any]] = []

    unverified: int | None = None
    writes_14: int | None = None
    cutover: date | None = None
    if deploys is not None:
        try:
            cutover = promotion_cutover(deploys[0])
        except OSError:
            pass  # waste names the unreadable deploy records
    try:
        writes = await _main_writes(gh, max(long_since, CUTOVER))
        if cutover is not None:
            # From the promotion cutover main is integration (ADR-171).
            writes = [w for w in writes if str(w.get("timestamp", "")) < _iso(cutover)]
        if not governor:
            unavailable.append(
                "governor's GitHub login: GOVERNOR_GITHUB not readable "
                "(CORE_GOVERNOR_GITHUB or the runner's pipeline.conf)"
            )
        else:
            prs = await _merged_prs(gh, max(long_since, CUTOVER))
            bad, pending = count_unverified(writes, prs, governor)
            judged = 0
            if deploys is not None and cutover is not None:
                bad_deploys, judged = await unverified_deploys(
                    gh, deploys[0], max(long_since, cutover), governor
                )
                bad += bad_deploys
            corrections = false_ci_breaches(kept, prs, governor, day)
            false_shas = {c["sha"] for c in corrections}
            kept = [b for b in kept if b["sha"] not in false_shas]
            known = {b["sha"] for b in kept} | false_shas
            new = [
                {**b, "first_seen": day.isoformat()}
                for b in bad
                if b["sha"] not in known
            ]
            kept += new
            unverified = len(kept)
            detail["unverified"] = {
                "writes": len(writes),
                "list": [f"{b['sha'][:12]} {b['reason']}" for b in kept],
                "new": len(new),
                "ci_pending": pending,
                "corrected": len(corrections),
                "promotion_cutover": cutover.isoformat() if cutover else None,
                "deploys_judged": judged,
            }
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
    try:
        readable = transcripts.is_dir() and os.access(transcripts, os.R_OK | os.X_OK)
    except OSError:  # a parent the daemon's user may not enter
        readable = False
    if not readable:
        unavailable.append(f"claude code transcripts: {transcripts} not readable")
    if deploys is not None:
        try:
            trips += deploy_trips(*deploys, waste_since)
        except OSError as exc:
            unavailable.append(f"deploy records: {exc}")
    deploys_read = not any(u.startswith("deploy records") for u in unavailable)
    github_read = not any(u.startswith("github") for u in unavailable)
    if readable and github_read and deploys_read:
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
        kept,
        corrections,
    )
