"""ADR-169 D4: three independent facts for every path changed between two
state observations -- governance provenance, producer provenance, persistence.

GitService.commits_between is exercised on a real repository: the author it
reports is git metadata, recorded as git-asserted and never authenticated.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from body.services.change_attribution import (
    UNREADABLE_RANGE_PATH,
    attribute_changes,
    load_proposal_claims,
)
from shared.infrastructure.git_service import GitService


def _git(repo: Path, *args: str, author: str = "Ann <ann@x>") -> str:
    name, _, email = author.partition(" <")
    return subprocess.run(
        [
            "git",
            "-c",
            f"user.name={name}",
            "-c",
            f"user.email={email.rstrip('>')}",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, rel: str, content: str, author: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel, author=author)
    _git(repo, "commit", "-q", "-m", f"edit {rel}", author=author)
    return _git(repo, "rev-parse", "HEAD")


def test_commits_between_lists_new_commits_oldest_first(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, "README", "r\n", "Ann <ann@x>")
    first = _commit(tmp_path, ".intent/rules/a.json", "{}\n", "Bob <bob@x>")
    second = _commit(tmp_path, "src/m.py", "x = 1\n", "Cy <cy@x>")

    commits = GitService(tmp_path).commits_between(base, second)

    assert commits == [
        (first, "Bob <bob@x>", [".intent/rules/a.json"]),
        (second, "Cy <cy@x>", ["src/m.py"]),
    ]
    assert GitService(tmp_path).commits_between(second, second) == []


def test_committed_changes_carry_three_independent_facts() -> None:
    commits = [
        ("s1", "Bob <bob@x>", [".intent/rules/a.json", "src/m.py"]),
        ("s2", "Cy <cy@x>", ["tests/t.py"]),
    ]
    claims = {("s1", "src/m.py"): "prop-1"}

    facts = attribute_changes("h0", [], "s2", [], commits, claims)

    by_path = {f.path: f for f in facts}
    law = by_path[".intent/rules/a.json"]
    assert (law.governance_provenance, law.producer_provenance, law.persistence) == (
        "direct",
        "git-asserted",
        "committed",
    )
    assert law.producer_identity == "Bob <bob@x>"
    governed = by_path["src/m.py"]
    assert governed.governance_provenance == "proposal"
    assert governed.proposal_id == "prop-1"
    # A proposal-produced commit still has an asserted author: independent facts.
    assert governed.producer_provenance == "git-asserted"
    assert by_path["tests/t.py"].commit_sha == "s2"


def test_git_author_is_never_reported_as_authenticated() -> None:
    facts = attribute_changes("h0", [], "s1", [], [("s1", "A <a@x>", ["f"])], {})
    assert {f.producer_provenance for f in facts} == {"git-asserted"}


def test_commit_without_author_is_unknown_producer() -> None:
    facts = attribute_changes("h0", [], "s1", [], [("s1", " <>", ["f"])], {})
    assert facts[0].producer_provenance == "unknown"
    assert facts[0].producer_identity is None


def test_newly_dirty_paths_are_uncommitted_and_unknown() -> None:
    facts = attribute_changes(
        "h", '["already.py"]', "h", ["already.py", ".intent/x.yaml"], [], {}
    )
    assert [
        (f.path, f.governance_provenance, f.producer_provenance, f.persistence)
        for f in facts
    ] == [(".intent/x.yaml", "unknown", "unknown", "uncommitted")]


def test_unreadable_commit_range_is_recorded_not_dropped() -> None:
    facts = attribute_changes("gone", [], "h1", [], None, {})
    assert len(facts) == 1
    assert facts[0].path == UNREADABLE_RANGE_PATH
    assert facts[0].producer_provenance == "unknown"
    assert facts[0].persistence == "committed"


def test_same_head_and_no_new_dirt_is_no_change() -> None:
    assert attribute_changes("h", ["a"], "h", ["a"], [], {}) == []


async def test_proposal_claims_accept_both_files_changed_shapes() -> None:
    result = MagicMock()
    result.fetchall.return_value = [
        ("p1", "s1", [{"path": "tests/a.py"}, "tests/b.py"]),
        ("p2", "s2", '["src/c.py"]'),
        ("p3", "s3", []),
    ]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    claims = await load_proposal_claims(session, ["s1", "s2", "s3"])

    assert claims == {
        ("s1", "tests/a.py"): "p1",
        ("s1", "tests/b.py"): "p1",
        ("s2", "src/c.py"): "p2",
    }


async def test_no_commits_means_no_claim_query() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    assert await load_proposal_claims(session, []) == {}
    session.execute.assert_not_awaited()
