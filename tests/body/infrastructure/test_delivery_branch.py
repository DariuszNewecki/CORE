# tests/body/infrastructure/test_delivery_branch.py
"""DeliveryBranch: CORE's generated tests are committed to
``refs/heads/core/test-gen``, never onto the clone's checked-out branch, so
the clone keeps fast-forwarding from upstream; they reach GitHub as one pull
request, or wait and say so when no token is configured.

Real git throughout: a local "upstream" on ``main`` and CORE's
clone on ``develop`` tracking it (the shape of /opt/core/repo).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import pytest

from body.infrastructure.delivery_branch import (
    DELIVERY_REF,
    PUSHED_REF,
    DeliveryBranch,
    deliver,
    delivers,
)
from body.infrastructure.repo_sync import RepoSync
from body.infrastructure.storage.file_handler import FileHandler
from shared.infrastructure.git_service import GitService


TEST_FILE = "tests/test_a.py"
PRODUCER = ("core:flow.build_test_for_symbol", "core-flow@core.invalid")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, body in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    up = tmp_path / "upstream"
    up.mkdir()
    _git(up, "init", "-q", "-b", "main")
    _commit(
        up, {".gitignore": "var/\n", "src/a.py": "def a():\n    return 1\n"}, "base"
    )
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--no-hardlinks", "-b", "main", str(up), "clone")
    _git(clone, "checkout", "-q", "-b", "develop")
    return up, clone


def _sync(clone: Path, up: Path) -> RepoSync:
    handler = FileHandler(str(clone))
    handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    return RepoSync(GitService(clone), handler, str(up))


def _generate(clone: Path, name: str, body: str) -> tuple[DeliveryBranch, object]:
    """What a delivered flow does: sandbox at the branch base, write the test
    there, commit it onto the branch."""
    git = GitService(clone)
    branch = DeliveryBranch(git)
    base = branch.base()
    sandbox = git.create_worktree(base)
    try:
        path = Path(sandbox.repo_path) / TEST_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text() if path.exists() else ""
        path.write_text(old + f"\n\ndef test_{name}():\n    {body}\n")
        done = branch.commit_from(
            sandbox, base, {TEST_FILE}, f"test: {name}", author=PRODUCER
        )
    finally:
        sandbox.cleanup()
    return branch, done


# ID: 3c7e9a14-5b2d-4f86-a1e0-8d6c2b9f4a51
def test_delivered_commit_leaves_head_develop_and_tree_unchanged(
    pair: tuple[Path, Path],
) -> None:
    _, clone = pair
    head = _git(clone, "rev-parse", "HEAD")
    develop = _git(clone, "rev-parse", "refs/heads/develop")

    branch, done = _generate(clone, "a", "assert True")

    assert done is not None and done.paths == [TEST_FILE]
    assert _git(clone, "rev-parse", "HEAD") == head
    assert _git(clone, "rev-parse", "refs/heads/develop") == develop
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""
    assert not (clone / TEST_FILE).exists()
    assert _git(clone, "rev-parse", DELIVERY_REF) == done.sha
    assert _git(clone, "rev-parse", f"{done.sha}^") == head
    assert "def test_a" in _git(clone, "show", f"{DELIVERY_REF}:{TEST_FILE}")
    author = _git(clone, "log", "-1", "--format=%an|%cn", DELIVERY_REF)
    assert author.startswith("core:flow.build_test_for_symbol|")
    assert branch.pending() == (1, [TEST_FILE])


# ID: 8a2f6d31-9c4e-4b75-b0d8-1e7a3f5c9b62
def test_second_test_builds_on_the_first(pair: tuple[Path, Path]) -> None:
    _, clone = pair
    _, first = _generate(clone, "a", "assert True")
    branch, second = _generate(clone, "b", "assert 1")
    assert second is not None and first is not None
    assert second.parent == first.sha
    text = _git(clone, "show", f"{DELIVERY_REF}:{TEST_FILE}")
    assert "def test_a" in text and "def test_b" in text
    assert branch.pending()[0] == 2


# ID: 5e1b8c47-2a9d-4f63-8e0b-7c4d1a6f2e93
def test_clone_keeps_fast_forwarding_after_delivery(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    branch, done = _generate(clone, "a", "assert True")
    assert done is not None

    # Someone else merges into main: the clone still follows by ff.
    moved = _commit(up, {"src/b.py": "def b():\n    return 2\n"}, "other work")
    outcome = _sync(clone, up).sync()
    assert outcome.state == "fast_forwarded"
    assert _git(clone, "rev-parse", "HEAD") == moved

    # The branch merges main in and still holds the waiting test.
    assert branch.follow()["state"] == "merged"
    assert _git(clone, "merge-base", "--is-ancestor", moved, DELIVERY_REF) == ""
    assert branch.pending() == (1, [TEST_FILE])

    # The pull request merges: main now holds the test, the clone
    # fast-forwards onto it and the branch has nothing left to deliver.
    _git(up, "fetch", "-q", str(clone), f"{DELIVERY_REF}:refs/heads/core/test-gen")
    _git(up, "merge", "-q", "--no-ff", "-m", "Merge PR", "core/test-gen")
    assert _sync(clone, up).sync().state == "fast_forwarded"
    assert "def test_a" in (clone / TEST_FILE).read_text()
    assert branch.follow()["state"] == "caught_up"
    assert branch.pending() == (0, [])
    # Every delivered commit is still on a branch (no orphaned consequence).
    assert _git(clone, "branch", "--contains", done.sha)


# ID: 9b4d2e78-6f1a-4c39-a5e7-3d8b0c2f6a14
def test_follow_drops_a_stale_change_upstream_also_made(
    pair: tuple[Path, Path],
) -> None:
    up, clone = pair
    branch, _ = _generate(clone, "a", "assert True")
    _commit(up, {TEST_FILE: "def test_upstream():\n    pass\n"}, "same file")
    assert _sync(clone, up).sync().state == "fast_forwarded"
    followed = branch.follow()
    assert followed == {"state": "merged", "dropped": [TEST_FILE]}
    assert _git(clone, "show", f"{DELIVERY_REF}:{TEST_FILE}") == (
        "def test_upstream():\n    pass"
    )
    assert branch.pending() == (0, [])


# ID: b3c5ae70-f45c-451b-974a-5fbfee2d1b7f
@pytest.mark.parametrize("main_moves", [True, False])
def test_follow_drops_a_generated_test_whose_module_main_deleted(
    pair: tuple[Path, Path], main_moves: bool
) -> None:
    """#1355: main deleted src/a.py while its generated test waited; the
    test could only fail to import, so follow gives main's tree back."""
    up, clone = pair
    git = GitService(clone)
    branch = DeliveryBranch(git)
    base = branch.base()
    generated = {
        "tests/a/__init__.py": "",
        "tests/a/test_generated.py": "from a import a\n",
        "tests/b/test_generated.py": "from b import b\n",
    }
    sandbox = git.create_worktree(base)
    try:
        for rel, body in generated.items():
            (Path(sandbox.repo_path) / rel).parent.mkdir(parents=True, exist_ok=True)
            (Path(sandbox.repo_path) / rel).write_text(body)
        branch.commit_from(sandbox, base, None, "test: a, b", author=PRODUCER)
    finally:
        sandbox.cleanup()

    _git(up, "rm", "-q", "src/a.py")
    _commit(up, {"src/b.py": "def b():\n    return 2\n"}, "remove a, add b")
    assert _sync(clone, up).sync().state == "fast_forwarded"
    if not main_moves:
        # The branch merged main before this fix: its tip already holds HEAD.
        merged = _git(clone, "merge-tree", "--write-tree", DELIVERY_REF, "HEAD")
        sha = _git(
            clone, "commit-tree", merged, "-p", DELIVERY_REF, "-p", "HEAD", "-m", "m"
        )
        _git(clone, "update-ref", DELIVERY_REF, sha)

    followed = branch.follow()

    assert followed == {
        "state": "merged" if main_moves else "current",
        "dropped": ["tests/a/__init__.py", "tests/a/test_generated.py"],
    }
    assert branch.pending()[1] == ["tests/b/test_generated.py"]
    assert branch.follow() == {"state": "current", "dropped": []}


# ID: 2d6a9f13-8e4b-4c71-b3a0-5f9e1c7d4b28
def test_pending_source_is_the_waiting_test_file(pair: tuple[Path, Path]) -> None:
    _, clone = pair
    branch = DeliveryBranch(GitService(clone))
    assert branch.pending_source(TEST_FILE) is None
    _generate(clone, "a", "assert True")
    assert "def test_a" in (branch.pending_source(TEST_FILE) or "")
    assert branch.pending_source("tests/test_other.py") is None


# ID: 7f3c1a95-4d8e-4b26-9a0f-6e2b8d5c1f47
def test_only_test_generation_is_delivered() -> None:
    assert delivers(["flow.build_test_for_symbol"])
    assert not delivers(["flow.fix_modularity"])
    assert not delivers(["flow.build_test_for_symbol", "fix.format"])
    assert not delivers([])


class _GitHub:
    """A stand-in for api.github.com recording what was asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, request.url.path, body))
        if request.url.path.endswith("/graphql"):
            return httpx.Response(200, json={"data": {"enable": {}}})
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(
            201, json={"number": 9, "node_id": "PR_9", "html_url": "https://x/pull/9"}
        )


async def _deliver(clone: Path, url: str, token: str | None, gh: _GitHub):
    git = GitService(clone)
    async with httpx.AsyncClient(transport=httpx.MockTransport(gh)) as client:
        return await deliver(
            DeliveryBranch(git),
            git,
            url=url,
            repo="owner/CORE",
            base_branch="main",
            token=token,
            client=client,
        )


# ID: 4a8e2c61-1f7b-4d93-b6e5-0c3a9d7f2b85
async def test_no_token_reports_waiting_and_pushes_nothing(
    pair: tuple[Path, Path],
) -> None:
    up, clone = pair
    _generate(clone, "a", "assert True")
    gh = _GitHub()
    outcome = await _deliver(clone, str(up), None, gh)
    assert outcome.state == "waiting"
    assert outcome.pending_commits == 1 and outcome.pending_files == 1
    assert "token" in (outcome.reason or "")
    assert gh.calls == []
    assert _git(up, "branch", "--list", "core/test-gen") == ""


# ID: 6c9b3e27-5a1d-4f84-8e2b-1d7f4a0c6e39
async def test_token_pushes_and_opens_one_pull_request(
    pair: tuple[Path, Path],
) -> None:
    up, clone = pair
    _generate(clone, "a", "assert True")
    _generate(clone, "b", "assert 1")
    gh = _GitHub()
    outcome = await _deliver(clone, str(up), "tok", gh)
    assert outcome.state == "delivered" and outcome.pr_url == "https://x/pull/9"
    assert _git(up, "rev-parse", "core/test-gen") == _git(
        clone, "rev-parse", DELIVERY_REF
    )
    posts = [c for c in gh.calls if c[0] == "POST" and c[1].endswith("/pulls")]
    assert len(posts) == 1
    assert posts[0][2]["head"] == "core/test-gen" and posts[0][2]["base"] == "main"
    assert posts[0][2]["title"].startswith("test: CORE-generated tests (")
    assert posts[0][2]["body"].startswith("3. Tests written autonomously by CORE")
    assert any(c[1].endswith("/graphql") for c in gh.calls)
    assert _git(clone, "rev-parse", PUSHED_REF) == _git(
        clone, "rev-parse", DELIVERY_REF
    )

    again = await _deliver(clone, str(up), "tok", gh)
    assert again.state == "current"
