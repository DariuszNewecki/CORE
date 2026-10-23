#!/usr/bin/env python3
"""The freeze-scope PR check (governor 2026-10-23, CLAUDE.md "Freeze until
2026-10-29").

Until FREEZE_END a pull request into main passes only when its description
names one of the v3 exit issues, or an issue in milestone CORE 3.1. Branches
promote/* (promotions) and core/test-gen (CORE's own tests) are exempt.
After FREEZE_END it always passes.

Run by .github/workflows/freeze-scope.yml with PR_BODY, HEAD_REF,
GITHUB_REPOSITORY and GITHUB_TOKEN set. Exit 0 passes, 1 fails.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request


FREEZE_END = dt.datetime(2026, 10, 29, 23, 59, tzinfo=dt.UTC)
EXIT_ISSUES = frozenset({1055, 1070, 1081, 1114, 1115, 1237, 1239, 1243, 1252, 1255})
NEXT_MILESTONE = "CORE 3.1"
EXEMPT_PREFIXES = ("promote/", "core/test-gen")
_REFERENCE = re.compile(r"(?<![\w/])#(\d+)(?!\d)|/issues/(\d+)(?!\d)")


def referenced(body: str) -> set[int]:
    """Issue numbers the description names: #N, or an /issues/N link."""
    return {int(a or b) for a, b in _REFERENCE.findall(body or "")}


def verdict(
    body: str, head_ref: str, now: dt.datetime, next_issues: set[int] | None
) -> tuple[bool, str]:
    """(passes, why). *next_issues* are the CORE 3.1 issue numbers, or None
    when they could not be read (then only an exit issue passes)."""
    if now > FREEZE_END:
        return True, f"the freeze ended at {FREEZE_END:%Y-%m-%d %H:%MZ}"
    if head_ref.startswith(EXEMPT_PREFIXES):
        return True, f"branch {head_ref} is exempt"
    refs = referenced(body)
    if refs & EXIT_ISSUES:
        return True, f"names v3 exit issue(s) {sorted(refs & EXIT_ISSUES)}"
    if next_issues and refs & next_issues:
        return True, f"names {NEXT_MILESTONE} issue(s) {sorted(refs & next_issues)}"
    unread = "" if next_issues is not None else f" ({NEXT_MILESTONE} not readable)"
    return False, (
        "the description names none of the v3 exit issues "
        f"{sorted(EXIT_ISSUES)} and no {NEXT_MILESTONE} issue{unread}. "
        "Freeze until 2026-10-29: see CLAUDE.md."
    )


def _get(url: str, token: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "freeze-scope",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def next_milestone_issues(repo: str, token: str) -> set[int] | None:
    """Every issue (open or closed) in milestone NEXT_MILESTONE, or None."""
    api = f"https://api.github.com/repos/{repo}"
    try:
        milestones = _get(f"{api}/milestones?state=all&per_page=100", token)
        (number,) = [m["number"] for m in milestones if m["title"] == NEXT_MILESTONE]
        issues: set[int] = set()
        page = 1
        while True:
            batch = _get(
                f"{api}/issues?milestone={number}&state=all&per_page=100&page={page}",
                token,
            )
            issues |= {int(i["number"]) for i in batch}
            if len(batch) < 100:
                return issues
            page += 1
    except Exception as exc:  # network, a renamed milestone
        print(f"freeze-scope: {NEXT_MILESTONE} not readable: {exc}", file=sys.stderr)
        return None


def main() -> int:
    now = dt.datetime.now(dt.UTC)
    head_ref = os.environ.get("HEAD_REF", "")
    body = os.environ.get("PR_BODY", "")
    issues: set[int] | None = set()
    if now <= FREEZE_END and not head_ref.startswith(EXEMPT_PREFIXES):
        if not referenced(body) & EXIT_ISSUES:
            issues = next_milestone_issues(
                os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
            )
    ok, why = verdict(body, head_ref, now, issues)
    print(f"freeze-scope: {'pass' if ok else 'FAIL'}: {why}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
