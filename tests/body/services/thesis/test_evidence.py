"""The evidence branch is append-only: a new file in a new commit on top of
the current head, never a force, never a rewrite of a week already there."""

from __future__ import annotations

import json

import httpx
import pytest

from body.services.thesis.github import GitHub, GitHubUnavailable
from body.services.thesis.record import push_evidence_week


class _GitHub:
    def __init__(self, head: str | None, existing: set[str] = frozenset()) -> None:
        self.head = head
        self.existing = existing
        self.calls: list[tuple[str, str, dict | None]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/repos/o/r/")
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body))
        if path == "git/ref/heads/evidence":
            if self.head is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"object": {"sha": self.head}})
        if path.startswith("contents/"):
            name = path.removeprefix("contents/")
            return httpx.Response(200 if name in self.existing else 404, json={})
        if path.startswith("git/commits/") and request.method == "GET":
            return httpx.Response(200, json={"tree": {"sha": "base-tree"}})
        if path == "git/trees":
            return httpx.Response(201, json={"sha": "new-tree"})
        if path == "git/commits":
            return httpx.Response(201, json={"sha": "new-commit"})
        if path in ("git/refs", "git/refs/heads/evidence"):
            return httpx.Response(200, json={})
        return httpx.Response(500)

    def writes(self) -> list[tuple[str, str, dict | None]]:
        return [c for c in self.calls if c[0] in ("POST", "PATCH")]


async def _push(fake: _GitHub, token: str | None = "t"):
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)) as c:
        return await push_evidence_week(
            GitHub("o/r", token, c), "2026-W42", [{"day": "2026-10-12"}]
        )


async def test_appends_on_top_of_the_head_without_force() -> None:
    fake = _GitHub(head="old-head")
    assert await _push(fake) == "new-commit"
    tree, commit, ref = fake.writes()
    assert tree[2]["base_tree"] == "base-tree"
    assert tree[2]["tree"][0]["path"] == "thesis/2026-W42.json"
    assert commit[2]["parents"] == ["old-head"]
    assert ref == (
        "PATCH",
        "git/refs/heads/evidence",
        {"sha": "new-commit", "force": False},
    )


async def test_first_push_creates_the_branch() -> None:
    fake = _GitHub(head=None)
    await _push(fake)
    _, commit, ref = fake.writes()
    assert commit[2]["parents"] == []
    assert ref == (
        "POST",
        "git/refs",
        {"ref": "refs/heads/evidence", "sha": "new-commit"},
    )


async def test_a_week_already_there_is_never_rewritten() -> None:
    fake = _GitHub(head="old-head", existing={"thesis/2026-W42.json"})
    assert await _push(fake) is None
    assert fake.writes() == []


async def test_no_token_writes_nothing() -> None:
    fake = _GitHub(head="old-head")
    with pytest.raises(GitHubUnavailable):
        await _push(fake, token=None)
    assert fake.writes() == []
