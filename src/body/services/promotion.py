# src/body/services/promotion.py
"""The daily promotion proposal (ADR-171): main's newest green commit as a
pull request into ``live``, with a plain-language summary for the governor.

Main is integration; only a promotion the governor approved runs live
(core-pipeline deploys it, core-deploy checks it). This builds the one open
promotion: it opens the pull request into ``live`` from the branch
``promote/<12 hex>`` at the candidate commit, or updates its text. The
summary lists the high-risk changes first (host and infra, law, database
migrations, login/permission/security paths), then the CI result and the last
sandbox check, then every merged pull request. An open promotion's head never
moves; a newer candidate replaces it with a new pull request, so the governor
approves exactly the head they read (review finding F13).

Everything goes through GitHub's REST API; no checkout is needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from body.services.thesis.github import GitHub, GitHubUnavailable


# Each proposal has its own branch, promote/<12 hex>: an open promotion's
# head never moves (review finding F13).
PROMOTE_PREFIX = "promote/"
LIVE_BRANCH = "live"
MAIN_BRANCH = "main"
GREEN = {"success", "skipped", "neutral"}
# How far back from main's head a green commit is looked for.
CANDIDATE_DEPTH = 5
MERGE_TITLE = re.compile(r"^Merge pull request #(\d+) ")

# High-risk classes, in the order the governor reads them (ADR-171).
RISK_CLASSES: tuple[tuple[str, str], ...] = (
    ("host", "Host and infra changes (run as root or set up the machine)"),
    ("law", "Law (.intent/)"),
    ("migration", "Database migrations"),
    ("security", "Login, permissions and security"),
    ("gates", "Checks and gates (what decides a verdict, and CI)"),
)
_SECURITY_PARTS = ("principal", "sandbox", "custody", "auth", "rbac", "secret")


# ID: e52e8a05-9a39-44c0-9beb-3c1422504702
def risk_class(path: str) -> str | None:
    """The high-risk class of a changed *path*, or None."""
    if path.startswith("infra/") and "migrations/" not in path:
        return "host"
    if path.startswith(".intent/"):
        return "law"
    # A change to a check, the governance engine or CI can loosen the gate
    # that judges every later change, so the governor reads it first.
    if (
        (path.startswith("src/mind/") and "/checks/" in path)
        or path.startswith("src/mind/governance/")
        or path.startswith(".github/workflows/")
    ):
        return "gates"
    if "migrations/" in path or path.endswith(".sql"):
        return "migration"
    lowered = path.lower()
    if path == "src/api/dependencies.py" or (
        path.startswith("src/") and any(p in lowered for p in _SECURITY_PARTS)
    ):
        return "security"
    return None


@dataclass
# ID: 7bede2de-839e-4859-9f57-226c67c65066
class Change:
    """One merged pull request in the promotion."""

    number: int
    title: str
    files: list[str] = field(default_factory=list)


@dataclass
# ID: 359084ea-907d-4bd4-8915-d7fc50e37265
class Proposal:
    """What a promotion would make live, and what the governor reads first."""

    candidate: str
    live: str
    ci: str
    sandbox: str
    changes: list[Change]
    urgent: bool = False
    skipped: list[str] = field(default_factory=list)  # newer, not green
    note: str | None = None  # how the live commit was found, when not certain
    alarms: list[str] = field(default_factory=list)  # open, for the governor

    # ID: 25857f55-4040-4548-836b-dedb63759435
    def risks(self) -> dict[str, list[tuple[Change, str]]]:
        found: dict[str, list[tuple[Change, str]]] = {k: [] for k, _ in RISK_CLASSES}
        for change in self.changes:
            for path in change.files:
                kind = risk_class(path)
                if kind:
                    found[kind].append((change, path))
        return found

    # ID: f875346a-3708-41c0-b27b-051fd6667f53
    def title(self) -> str:
        prefix = "Urgent promotion" if self.urgent else "Promotion"
        return f"{prefix}: main at {self.candidate[:12]} ({len(self.changes)} changes)"

    # ID: c2f9c7bd-4ce1-46e4-ad2c-89e4c6a77817
    def body(self) -> str:
        short, live = self.candidate[:12], self.live[:12]
        lines = [
            f"Makes main at `{short}` live (now `{live}`): "
            f"{len(self.changes)} merged pull request(s).",
        ]
        if self.note:
            lines += ["", f"**Note:** {self.note}"]
        if self.alarms:
            lines += ["", "## CORE needs you first"]
            lines += [f"- {alarm}" for alarm in self.alarms]
        lines += [
            "",
            "## Look at these first",
        ]
        risks = self.risks()
        if not any(risks.values()):
            lines.append("No high-risk changes.")
        for kind, label in RISK_CLASSES:
            if not risks[kind]:
                continue
            lines.append(f"**{label}**")
            for change, path in risks[kind]:
                lines.append(f"- `{path}` — #{change.number} {change.title}")
        lines += [
            "",
            "## Checks",
            f"- CI on `{short}`: {self.ci}",
            f"- Sandbox check: {self.sandbox}",
        ]
        if self.skipped:
            lines.append(
                "- Newer main commits not proposed (CI not green yet): "
                + ", ".join(f"`{s[:12]}`" for s in self.skipped)
            )
        lines += ["", "## All changes"]
        lines += [f"- #{c.number} {c.title}" for c in self.changes] or ["- (none)"]
        lines += [
            "",
            "## Your decision",
            f"- **Approve** this pull request's last commit to make `{short}` live.",
            "- **Reject** by closing it: nothing goes live. Nothing is reverted "
            "on main, so the next daily proposal carries these changes again; "
            "to keep one out of live, name it and it is reverted on main by a "
            "pull request.",
        ]
        return "\n".join(lines) + "\n"


async def _ci(gh: GitHub, sha: str) -> str:
    data = await gh.get(f"commits/{sha}/check-runs?per_page=100")
    latest: dict[Any, dict] = {}
    for i, run in enumerate(data.get("check_runs", [])):
        key = ((run.get("app") or {}).get("id"), run.get("name"))
        if run.get("name") is None or not isinstance(run.get("id"), int):
            key = ("unnamed", i)
        if key not in latest or run["id"] > latest[key]["id"]:
            latest[key] = run
    runs = list(latest.values())
    if not runs or any(r.get("status") != "completed" for r in runs):
        return "pending"
    if any(r.get("conclusion") not in GREEN for r in runs):
        return "red"
    return "green"


def _sandbox_line(pipeline: dict[str, Any] | None) -> str:
    """The sandbox check runs after a deploy (core-pipeline); a failure rolls
    the deploy back. Its last outcome, from the runner's status."""
    last = (pipeline or {}).get("last") or {}
    rule = "runs right after the deploy; a failure rolls it back"
    if last.get("result") == "live":
        return f"{rule}. Last deploy (`{str(last.get('sha'))[:12]}`): passed"
    if last.get("result") == "failed":
        return (
            f"{rule}. Last deploy (`{str(last.get('sha'))[:12]}`): {last.get('what')}"
        )
    return f"{rule}. No earlier result"


# ID: 8193c2dd-f239-4912-9e8c-00536d3f71eb
async def live_commit(
    gh: GitHub, pipeline: dict[str, Any] | None
) -> tuple[str | None, str | None]:
    """(the commit a promotion starts from, a note for the summary or None).

    The deployed commit, from core-pipeline's status: the ``live`` branch
    does not move without the runner's token. The branch is the fallback
    only when the status is unreadable, and the summary then says so."""
    deployed = (pipeline or {}).get("live")
    if deployed:
        return str(deployed), None
    ref = await gh.get_or_none(f"git/ref/heads/{LIVE_BRANCH}")
    if ref is None:
        return None, None
    return str(ref["object"]["sha"]), (
        "core-pipeline's status could not be read, so this proposal starts "
        f"from the `{LIVE_BRANCH}` branch, which can lag the deployed commit; "
        "it may list changes that are already live."
    )


# ID: b5035d18-53a2-439a-98b5-284af5729f2f
async def build_proposal(
    gh: GitHub,
    live: str,
    pipeline: dict[str, Any] | None = None,
    urgent: bool = False,
    note: str | None = None,
    alarms: list[str] | None = None,
) -> Proposal | None:
    """The proposal for main's newest green first-parent commit since *live*;
    None when main has nothing new, or nothing new is green."""
    compare = await gh.get(f"compare/{live}...{MAIN_BRANCH}")
    if compare.get("status") != "ahead" or not compare.get("commits"):
        return None
    merges = [
        c
        for c in compare["commits"]
        if MERGE_TITLE.match((c.get("commit") or {}).get("message", ""))
    ]
    # Newest first; first-parent merges are where main can be promoted.
    skipped: list[str] = []
    candidate = None
    for commit in reversed(merges[-CANDIDATE_DEPTH:]):
        state = await _ci(gh, commit["sha"])
        if state == "green":
            candidate = commit
            break
        skipped.append(commit["sha"])
    if candidate is None:
        return None
    upto = merges[: merges.index(candidate) + 1]
    changes = []
    for commit in upto:
        match = MERGE_TITLE.match(commit["commit"]["message"])
        assert match
        number = int(match.group(1))
        pull = await gh.get(f"pulls/{number}")
        files = await gh.get_pages(f"pulls/{number}/files?per_page=100")
        changes.append(
            Change(
                number, str(pull.get("title", "")), [str(f["filename"]) for f in files]
            )
        )
    return Proposal(
        candidate=str(candidate["sha"]),
        live=live,
        ci="green",
        sandbox=_sandbox_line(pipeline),
        changes=changes,
        urgent=urgent,
        skipped=skipped,
        note=note,
        alarms=list(alarms or []),
    )


# ID: d27aa239-894c-4adf-bc11-a33c7290bf70
async def publish(gh: GitHub, proposal: Proposal) -> str:
    """Open the promotion pull request for the candidate, on its own branch
    ``promote/<12 hex>``, or update the text of the one already open for it.
    Returns the pull request's URL.

    An open promotion's head never moves (review finding F13): an approval
    lands on the commit the governor read. A newer candidate gets a new pull
    request; the older open ones are closed and their branches deleted, so
    no approval can land on them. One whose head is the deployed commit is
    left open: GitHub marks it merged once ``live`` catches up."""
    pulls = await gh.get(f"pulls?state=open&base={LIVE_BRANCH}&per_page=100")
    promotions = [
        p
        for p in pulls
        if str((p.get("head") or {}).get("ref") or "").startswith(PROMOTE_PREFIX)
    ]
    content = {"title": proposal.title(), "body": proposal.body()}
    for pull in promotions:
        if pull["head"].get("sha") == proposal.candidate:
            updated = await gh.send("PATCH", f"pulls/{pull['number']}", content)
            return str(updated.get("html_url"))
    branch = f"{PROMOTE_PREFIX}{proposal.candidate[:12]}"
    if await gh.get_or_none(f"git/ref/heads/{branch}") is None:
        await gh.send(
            "POST",
            "git/refs",
            {"ref": f"refs/heads/{branch}", "sha": proposal.candidate},
        )
    opened = await gh.send(
        "POST", "pulls", {**content, "head": branch, "base": LIVE_BRANCH}
    )
    for pull in promotions:
        if pull["head"].get("sha") == proposal.live:
            continue
        await gh.send("PATCH", f"pulls/{pull['number']}", {"state": "closed"})
        await gh.delete(f"git/refs/heads/{pull['head']['ref']}")
    return str(opened.get("html_url"))


__all__ = [
    "GitHubUnavailable",
    "Proposal",
    "build_proposal",
    "live_commit",
    "publish",
    "risk_class",
]
