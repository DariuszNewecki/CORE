# src/body/services/thesis/record.py
"""Where the thesis measures are kept.

Daily: one blackboard report per day, subject ``thesis.measures::<date>``,
payload the four numbers, their breaches and the governor's line (posted by
the thesis sensor). Weekly: the week's daily records as one new file,
``thesis/<year>-W<week>.json``, on the GitHub branch ``evidence``. That
branch is append-only: each push adds a file in a new commit on top of the
current head (``force: false``), and a week already there is never written
again. Force-pushes and deletion are refused by the branch's ruleset.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from body.services.thesis.github import GitHub
from shared.thesis_rules import EVIDENCE_SUBJECT, MEASURES_SUBJECT


EVIDENCE_BRANCH = "evidence"


# ID: 8e0d162b-82a6-472b-b513-516dcdbbfff3
async def daily_records(since: date | None = None) -> list[dict[str, Any]]:
    """Stored daily reports, oldest first (payloads), optionally from *since*."""
    from sqlalchemy import text

    from body.services.service_registry import ServiceRegistry

    async with ServiceRegistry.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT payload FROM core.blackboard_entries "
                    "WHERE entry_type = 'report' AND subject LIKE :prefix "
                    "ORDER BY created_at"
                ),
                {"prefix": f"{MEASURES_SUBJECT}%"},
            )
        ).all()
    records = [dict(row[0]) for row in rows if isinstance(row[0], dict)]
    if since is not None:
        records = [r for r in records if str(r.get("day", "")) >= since.isoformat()]
    return records


# ID: 4a902cee-9c70-4d93-aa6a-2ed2100f9385
async def evidence_weeks() -> set[str]:
    """Weeks the sensor has recorded as pushed to the evidence branch."""
    from sqlalchemy import text

    from body.services.service_registry import ServiceRegistry

    async with ServiceRegistry.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT subject FROM core.blackboard_entries "
                    "WHERE entry_type = 'report' AND subject LIKE :prefix"
                ),
                {"prefix": f"{EVIDENCE_SUBJECT}%"},
            )
        ).all()
    return {str(row[0]).removeprefix(EVIDENCE_SUBJECT) for row in rows}


# ID: 2ed9f0ea-ad15-4a5d-b27e-b963f6903988
async def push_evidence_week(
    gh: GitHub, week: str, records: list[dict[str, Any]]
) -> str | None:
    """Append ``thesis/<week>.json`` to the evidence branch in a new commit.

    Returns the new commit's sha, or None when that week is already on the
    branch (append-only: an existing file is never rewritten). Creates the
    branch, as a root commit, on its first push.
    """
    path = f"thesis/{week}.json"
    head = await gh.get_or_none(f"git/ref/heads/{EVIDENCE_BRANCH}")
    parent = str(head["object"]["sha"]) if head else None
    tree_request: dict[str, Any] = {
        "tree": [
            {
                "path": path,
                "mode": "100644",
                "type": "blob",
                "content": json.dumps(
                    {"week": week, "days": records}, indent=2, sort_keys=True
                )
                + "\n",
            }
        ]
    }
    if parent:
        if await gh.get_or_none(f"contents/{path}?ref={EVIDENCE_BRANCH}") is not None:
            return None
        commit = await gh.get(f"git/commits/{parent}")
        tree_request["base_tree"] = commit["tree"]["sha"]
    tree = await gh.send("POST", "git/trees", tree_request)
    new = await gh.send(
        "POST",
        "git/commits",
        {
            "message": f"evidence: thesis measures {week}",
            "tree": tree["sha"],
            "parents": [parent] if parent else [],
        },
    )
    if parent:
        await gh.send(
            "PATCH",
            f"git/refs/heads/{EVIDENCE_BRANCH}",
            {"sha": new["sha"], "force": False},
        )
    else:
        await gh.send(
            "POST",
            "git/refs",
            {"ref": f"refs/heads/{EVIDENCE_BRANCH}", "sha": new["sha"]},
        )
    return str(new["sha"])
