# tests/proof_index/attestation_queries.py
"""Live queries behind the attestation halves of proof-index claims 4 and 6.

Read-only; not a test (needs the live PostgreSQL). The governor runs it as
``core`` with the live release and posts the output on #798:

    sudo systemd-run --user -M core@ --collect --quiet --wait --pipe \\
      --property=EnvironmentFile=/opt/core/etc/core.env \\
      --property=WorkingDirectory=/opt/core/run \\
      /opt/core/current/venv/bin/python -I - < tests/proof_index/attestation_queries.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session


# id is a uuid: order by time, not id.
AUDIT = """
SELECT action_type, ok, agent_id, created_at FROM core.action_results
WHERE agent_id = 'ActionExecutor' ORDER BY created_at DESC LIMIT 5"""

AUDIT_30D = """
SELECT count(*) AS rows_last_30_days, max(created_at) AS newest FROM core.action_results
WHERE agent_id = 'ActionExecutor' AND created_at > now() - interval '30 days'"""

CHAIN = """
SELECT ap.goal, ap.approved_by, ap.approval_authority,
       left(pc.pre_execution_sha, 8) AS pre, left(pc.post_execution_sha, 8) AS post,
       (SELECT string_agg(f->>'path', ', ') FROM jsonb_array_elements(pc.files_changed) f) AS files,
       pc.recorded_at
FROM core.proposal_consequences pc
JOIN core.autonomous_proposals ap ON ap.proposal_id = pc.proposal_id
WHERE pc.post_execution_sha IS DISTINCT FROM pc.pre_execution_sha
ORDER BY pc.recorded_at DESC LIMIT 5"""

CHAIN_COUNTS = """
SELECT count(*) AS executions,
       count(*) FILTER (WHERE post_execution_sha IS DISTINCT FROM pre_execution_sha) AS with_a_commit,
       max(recorded_at) FILTER (WHERE post_execution_sha IS DISTINCT FROM pre_execution_sha) AS newest_commit
FROM core.proposal_consequences"""


async def main():
    async with get_session() as s:
        print("== claim 4: audit trail (newest 5)")
        for r in (await s.execute(text(AUDIT))).all():
            print(r)
        print(dict((await s.execute(text(AUDIT_30D))).mappings().one()))
        print("== claim 6: consequence chains that changed a commit (newest 5)")
        for r in (await s.execute(text(CHAIN))).mappings().all():
            print(dict(r))
        print(dict((await s.execute(text(CHAIN_COUNTS))).mappings().one()))


asyncio.run(main())
