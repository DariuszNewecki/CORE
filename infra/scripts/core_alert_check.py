#!/usr/bin/env python3
"""Tell the governor when the deploy pipeline is failing (review finding F4).

core-pipeline catches its errors and writes them to its status file; the
issue it opens itself goes out with the governor's own token, and GitHub
sends no email for one's own issue. This check runs every 15 minutes from
core-claude's crontab, as core-claude-bot (the gh login on the closed
credential list), and keeps exactly one open issue per problem, mentioning
the governor so GitHub emails them:

- ``pipeline-error``: the last tick failed (status ``state`` is ``error``);
- ``pipeline-stalled``: no tick wrote the status for STALL_AFTER, or the
  status file cannot be read;
- ``promotion-failed-<sha12>``: the last promotion did not go live.

An issue already open for a problem is left as it is (no new issue, no new
comment); when the problem is gone it gets a "cleared" comment and is
closed. The gh login is checked by a real call before anything relies on it.

    crontab: */15 * * * * live=$(basename "$(readlink -f /opt/core/current)") && git -C /opt/dev/CORE show "$live:infra/scripts/core_alert_check.py" | python3 -I - >> "$HOME/.cache/core-alert-check.log" 2>&1

``--test`` opens one test alert, to prove the email arrives; the next run
without ``--test`` closes it.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


REPO = "DariuszNewecki/CORE"
GOVERNOR = "DariuszNewecki"
STATUS = Path("/var/lib/core-pipeline/status.json")
STALL_AFTER = dt.timedelta(minutes=15)
PREFIX = "[alert] "


def problems(status: dict | None, now: dt.datetime) -> dict[str, str]:
    """{key: plain-words text} for each problem *status* shows at *now*."""
    if status is None:
        return {"pipeline-stalled": "core-pipeline's status file cannot be read."}
    found: dict[str, str] = {}
    at = status.get("at")
    try:
        age = now - dt.datetime.fromisoformat(str(at))
    except ValueError:
        age = None
    if age is None or age > STALL_AFTER:
        found["pipeline-stalled"] = (
            f"core-pipeline has not written its status since {at}: "
            "the timer or the runner is not running."
        )
    if status.get("state") == "error":
        found["pipeline-error"] = (
            f"core-pipeline's last run failed: {status.get('error', 'no detail')}"
        )
    last = status.get("last") or {}
    if last.get("result") == "failed" and last.get("sha"):
        sha = str(last["sha"])
        found[f"promotion-failed-{sha[:12]}"] = (
            f"Promotion #{last.get('promotion')} of {sha[:12]} did not go live: "
            f"{last.get('what')}. Details: {last.get('issue') or 'the deploy log'}."
        )
    return found


def _gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def _open_alerts() -> dict[str, int]:
    """{key: issue number} of the open alert issues core-claude-bot opened."""
    out = _gh(
        "issue",
        "list",
        "--repo",
        REPO,
        "--state",
        "open",
        "--author",
        "@me",
        "--search",
        "alert in:title",
        "--json",
        "number,title",
        "--limit",
        "100",
    )
    alerts: dict[str, int] = {}
    for issue in json.loads(out):
        title = str(issue["title"])
        if title.startswith(PREFIX):
            alerts[title[len(PREFIX) :].split(":", 1)[0]] = int(issue["number"])
    return alerts


def reconcile(found: dict[str, str], open_alerts: dict[str, int], gh=_gh) -> list[str]:
    """Open an issue for each new problem, close the ones that cleared.
    Returns what was done, one line each."""
    done: list[str] = []
    for key, text in found.items():
        if key in open_alerts:
            continue
        gh(
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            f"{PREFIX}{key}: {text[:80]}",
            "--body",
            f"@{GOVERNOR} {text}\n\nThis issue closes by itself when the "
            "problem is gone (infra/scripts/core_alert_check.py, review F4).",
        )
        done.append(f"opened {key}")
    for key, number in open_alerts.items():
        if key not in found:
            gh(
                "issue",
                "close",
                str(number),
                "--repo",
                REPO,
                "--comment",
                "Cleared: the problem is gone.",
            )
            done.append(f"closed {key} (#{number})")
    return done


def _status() -> dict | None:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str]) -> int:
    now = dt.datetime.now(dt.UTC)
    if _gh("api", f"repos/{REPO}", "--jq", ".permissions.push").strip() != "true":
        print(f"{now:%FT%TZ} core-alert-check: the gh login cannot write to {REPO}")
        return 1
    found = problems(_status(), now)
    if "--test" in argv:
        found["test"] = "Test alert: if this reached your inbox, alerts work."
    for line in reconcile(found, _open_alerts()) or ["nothing to do"]:
        print(f"{now:%FT%TZ} core-alert-check: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
