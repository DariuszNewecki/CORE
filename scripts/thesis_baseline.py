#!/usr/bin/env python3
"""scripts/thesis_baseline.py — the four thesis measures, on demand.

Read-only. The same code the daily thesis sensor runs
(body.services.thesis.measure), pointed at the development checkout: git log
of origin/main, the GitHub token of the logged-in `gh`, the blackboard
through the checkout's .env, Claude Code's transcripts for this project, and
the deploy ledger with the runner's logs: from the first deploy recorded with
its promotion (ADR-171) the unverified writes are the deploys that ran no
governor-approved promotion, not writes to main.
The thesis and its rules: .specs/DECISIONS.md, "Thesis and baselines
(2026-10-13)". A source that cannot be read is reported, never counted as
zero.

    cd /opt/dev/CORE && PYTHONPATH=src .venv/bin/python scripts/thesis_baseline.py
    ... --day 2026-10-13 --json
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import subprocess
from pathlib import Path

import httpx

from body.infrastructure.thesis_config import thesis_config
from body.services.thesis.github import GitHub
from body.services.thesis.measure import measure
from shared.infrastructure.git_service import GitService
from shared.thesis_rules import report_line


REPO = "DariuszNewecki/CORE"
ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = Path.home() / ".claude" / "projects" / "-opt-dev-CORE"


def _token() -> str | None:
    done = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    return done.stdout.strip() or None


async def _measure(day: dt.date):
    from body.services.service_registry import ServiceRegistry
    from shared.infrastructure.database.session_manager import get_session

    ServiceRegistry.prime(get_session)
    config = thesis_config()
    async with httpx.AsyncClient() as client:
        return await measure(
            day,
            GitHub(REPO, _token(), client),
            GitService(ROOT),
            "origin/main",
            TRANSCRIPTS,
            deploys=(config.deploy_ledger, config.pipeline_logs),
            governor=config.governor,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--day", type=dt.date.fromisoformat, default=dt.datetime.now(dt.UTC).date()
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    taken = asyncio.run(_measure(args.day))
    if args.json:
        print(
            json.dumps(
                {
                    **taken.measures.as_payload(),
                    "detail": taken.detail,
                    "unavailable": taken.unavailable,
                },
                indent=2,
            )
        )
        return
    print(report_line(taken.measures))
    for source in taken.unavailable:
        print(f"  unavailable: {source}")


if __name__ == "__main__":
    main()
