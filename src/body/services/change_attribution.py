# src/body/services/change_attribution.py
"""
Change attribution — what CORE knows about every change between two state
observations (ADR-169 D4).

For each path that changed between two ledger observations, three
**independent** facts are recorded. They are not one taxonomy: a
proposal-produced commit also has an author; a direct commit can be
attributable without being governed.

- governance provenance: ``proposal`` (the path is in the
  ``proposal_consequences.files_changed`` of the proposal whose
  post-execution commit it is) / ``direct`` (committed outside any proposal) /
  ``unknown`` (not determinable, e.g. uncommitted);
- producer provenance: ``git-asserted`` (the commit's author metadata —
  asserted, NOT authenticated: anyone able to commit can set it) /
  ``authenticated`` (reserved for #942 / ADR-132 D10; never produced here) /
  ``unknown`` (no commit, or no author);
- persistence: ``committed`` / ``uncommitted``.

Committed changes come from the commits between the two observations' HEADs.
Uncommitted changes are the paths dirty now that were not dirty at the
previous observation (a further edit to an already-dirty path is not visible
without content hashes; it is recorded when committed).

Pure functions plus one read query. Constitutional standing: body/services.
No LLM calls. No file writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)

GovernanceProvenance = Literal["proposal", "direct", "unknown"]
ProducerProvenance = Literal["authenticated", "git-asserted", "unknown"]
Persistence = Literal["committed", "uncommitted"]

# Recorded when the commit range between two observations cannot be read
# (e.g. the previous HEAD no longer exists after a history rewrite): the
# change is known to exist, its paths are not.
UNREADABLE_RANGE_PATH = "(commit range unreadable)"


@dataclass(frozen=True)
# ID: 61ff0fac-89ff-4935-a5f4-0048dcd9fa5e
class ChangeFact:
    """One changed path and the three D4 facts about it."""

    path: str
    governance_provenance: GovernanceProvenance
    producer_provenance: ProducerProvenance
    persistence: Persistence
    commit_sha: str | None = None
    producer_identity: str | None = None
    proposal_id: str | None = None


def _paths(value: Any) -> set[str]:
    if isinstance(value, str):
        value = json.loads(value)
    return set(value or [])


# ID: 81758f66-4bc9-41d4-97a4-974f5bfc3850
def attribute_changes(
    previous_head: str | None,
    previous_dirty: Any,
    head: str | None,
    dirty: list[str],
    commits: list[tuple[str, str, list[str]]] | None,
    proposal_claims: dict[tuple[str, str], str],
) -> list[ChangeFact]:
    """The D4 facts for every path that changed between two observations.

    ``commits`` is ``GitService.commits_between(previous_head, head)``, or
    None when that range could not be read. ``proposal_claims`` maps
    ``(commit_sha, path)`` to the proposal that declared it.
    """
    facts: list[ChangeFact] = []
    if previous_head and head and previous_head != head:
        if commits is None:
            facts.append(
                ChangeFact(
                    path=UNREADABLE_RANGE_PATH,
                    governance_provenance="unknown",
                    producer_provenance="unknown",
                    persistence="committed",
                    commit_sha=head,
                )
            )
        else:
            for sha, author, paths in commits:
                identity = author if author.strip(" <>") else None
                for path in paths:
                    proposal_id = proposal_claims.get((sha, path))
                    facts.append(
                        ChangeFact(
                            path=path,
                            governance_provenance=(
                                "proposal" if proposal_id else "direct"
                            ),
                            producer_provenance=(
                                "git-asserted" if identity else "unknown"
                            ),
                            persistence="committed",
                            commit_sha=sha,
                            producer_identity=identity,
                            proposal_id=proposal_id,
                        )
                    )
    for path in sorted(set(dirty) - _paths(previous_dirty)):
        facts.append(
            ChangeFact(
                path=path,
                governance_provenance="unknown",
                producer_provenance="unknown",
                persistence="uncommitted",
            )
        )
    return facts


# ID: f9d95570-f491-493f-8408-5e2c15cd29b2
async def load_proposal_claims(
    session: Any, commit_shas: list[str]
) -> dict[tuple[str, str], str]:
    """``{(commit_sha, path): proposal_id}`` from core.proposal_consequences.

    A path is claimed by a proposal only when it is in that proposal's
    ``files_changed`` AND the commit is the proposal's post-execution commit.
    ``files_changed`` entries are path strings or ``{"path": ...}`` objects.
    """
    if not commit_shas:
        return {}
    result = await session.execute(
        text(
            """
            SELECT proposal_id, post_execution_sha, files_changed
            FROM core.proposal_consequences
            WHERE post_execution_sha = ANY(:shas)
            """
        ),
        {"shas": commit_shas},
    )
    claims: dict[tuple[str, str], str] = {}
    for proposal_id, sha, files_changed in result.fetchall():
        entries = (
            json.loads(files_changed)
            if isinstance(files_changed, str)
            else files_changed
        )
        for entry in entries or []:
            path = entry.get("path") if isinstance(entry, dict) else entry
            if isinstance(path, str) and path:
                claims[(sha, path)] = str(proposal_id)
    return claims
