# src/body/infrastructure/delivery_branch.py
"""
DeliveryBranch — CORE's generated tests travel on a branch, never on HEAD.

CORE's clone follows upstream by fast-forward only (RepoSync). A commit made
on the clone's checked-out branch makes the two lines diverge at the next
merge into main, and the clone then audits stale code (2026-10-20: 109 test
commits on ``develop`` had to be rescued by hand). So a delivered flow's
commit goes to ``refs/heads/core/test-gen`` instead, a branch nobody checks
out:

* the flow's sandbox worktree starts at the branch tip (the branch first
  merges HEAD in, so it holds today's code plus every test still waiting),
  and the generated test is validated there;
* its files are written as blobs and committed onto the tip with git
  plumbing (a throwaway index): HEAD, the index and the working tree of the
  clone never change;
* when main moves, the branch merges it (``follow``); a path both sides
  changed takes main's version — CORE's stale change to it is dropped and
  logged, and the symbol becomes a gap again; a waiting generated test
  whose source module main deleted is dropped the same way (it could only
  fail to import);
* with a GitHub token the branch is pushed and ONE pull request into main
  carries everything waiting (``deliver``); without one the commits wait on
  the local branch and the caller reports how many.

Merging (not rebasing) keeps every recorded commit reachable from a branch,
so the commit reachability auditor sees no orphans, and a merged pull
request makes the branch an ancestor of main: the next ``follow`` simply
moves it to main.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.git_service import autonomous_identity
from shared.infrastructure.intent.test_coverage_paths import (
    load_test_coverage_config,
)
from shared.logger import getLogger


if TYPE_CHECKING:
    import httpx

    from shared.infrastructure.git_service import GitService


logger = getLogger(__name__)

DELIVERY_BRANCH = "core/test-gen"
DELIVERY_REF = f"refs/heads/{DELIVERY_BRANCH}"
# The tip last pushed and proposed; a cycle with nothing new skips GitHub.
PUSHED_REF = "refs/core/test-gen-pushed"
DELIVERED_FLOWS = frozenset({"flow.build_test_for_symbol"})
_PR_FILE_LIST_MAX = 100


# ID: 0b6e2f94-7c1a-4d58-9e3b-5a8d1c4f7e20
def delivers(flow_ids: Iterable[str]) -> bool:
    """True when every one of a proposal's flows commits to the delivery branch."""
    ids = list(flow_ids)
    return bool(ids) and all(i in DELIVERED_FLOWS for i in ids)


@dataclass(frozen=True)
# ID: 5d1a8c3e-9f2b-4e67-a0c4-7b3e6d9f1a82
class Delivered:
    """One delivery commit: its parent (the old tip or HEAD), itself, its paths."""

    parent: str
    sha: str
    paths: list[str]


# ID: e8c4a7f1-2d5b-4a93-b6e0-1f9d3c5a8b74
class DeliveryBranch:
    """CORE's own branch of generated tests on its clone (see module doc)."""

    def __init__(self, git: GitService) -> None:
        self._git = git
        # The commits this instance made (one proposal's, in order).
        self.delivered: list[Delivered] = []

    # ID: 4a9e1d6c-3b8f-4c25-9d7a-6e2f0b5c8a13
    def tip(self) -> str | None:
        """The branch tip, or None while nothing was ever delivered."""
        return self._git.resolve_ref(DELIVERY_REF)

    # ID: b3f7c2e9-8a1d-4f64-a5b0-9c6e3d1f7a28
    def follow(self, target: str | None = None) -> dict[str, Any]:
        """Bring the branch onto ``target`` (default HEAD) by merging it.

        ``none``: no branch; ``current``: it already contains target;
        ``caught_up``: everything it held reached target (moved there);
        ``merged``: target merged in, ``dropped`` naming the paths where
        target's version replaced CORE's stale change.
        """
        target = target or self._git.get_current_commit()
        tip = self.tip()
        if tip is None:
            return {"state": "none", "dropped": []}
        if self._git.is_ancestor(target, tip):
            return {"state": "current", "dropped": self._drop_orphans(target)}
        if self._git.is_ancestor(tip, target):
            self._git.update_ref(DELIVERY_REF, target, tip)
            return {"state": "caught_up", "dropped": []}
        tree, conflicts = self._git.merge_tree(tip, target)
        message = f"Merge {target[:12]} into {DELIVERY_BRANCH}"
        if conflicts:
            upstream = {p: self._git.ls_tree_blobs(target, p).get(p) for p in conflicts}
            tree = self._git.tree_with(tree, upstream)
            message += (
                "\n\nUpstream changed the same file; CORE's stale change was "
                "dropped:\n" + "\n".join(f"- {p}" for p in conflicts)
            )
            logger.warning(
                "DeliveryBranch: dropped CORE's stale change to %d path(s) "
                "upstream also changed: %s",
                len(conflicts),
                conflicts,
            )
        sha = self._git.commit_tree(
            tree, [tip, target], message, identity=autonomous_identity()
        )
        self._git.update_ref(DELIVERY_REF, sha, tip)
        return {"state": "merged", "dropped": conflicts + self._drop_orphans(target)}

    def _drop_orphans(self, target: str) -> list[str]:
        """Give ``target``'s version back to every waiting path under a
        generated test's directory whose source module ``target`` lacks
        (#1355: a test for a deleted module stops pytest collection)."""
        tip = self.tip()
        if tip is None:
            return []
        config = load_test_coverage_config()
        test_prefix = f"{config.get('test_root', 'tests')}/"
        suffix = config.get("test_file_suffix", "/test_generated.py")
        source_root = config.get("source_root", "src")
        pending = self._git.diff_names(target, tip)
        tests = [p for p in pending if p.startswith(test_prefix) and p.endswith(suffix)]
        if not tests:
            return []
        sources = self._git.ls_tree_blobs(target, source_root)
        orphan_dirs = [
            p[: -len(suffix)] + "/"
            for p in tests
            if f"{source_root}/{p[len(test_prefix) : -len(suffix)]}.py" not in sources
        ]
        dropped = sorted(
            p for p in pending if any(p.startswith(d) for d in orphan_dirs)
        )
        if not dropped:
            return []
        upstream = {p: self._git.ls_tree_blobs(target, p).get(p) for p in dropped}
        tree = self._git.tree_with(tip, upstream)
        message = (
            f"Drop generated tests whose source {target[:12]} removed\n\n"
            + "\n".join(f"- {p}" for p in dropped)
        )
        sha = self._git.commit_tree(
            tree, [tip], message, identity=autonomous_identity()
        )
        self._git.update_ref(DELIVERY_REF, sha, tip)
        logger.warning(
            "DeliveryBranch: dropped %d waiting path(s) whose source module "
            "is gone: %s",
            len(dropped),
            dropped,
        )
        return dropped

    # ID: 7c2d5a9f-1e6b-4d38-8f4a-3b0e9c7d2a56
    def base(self) -> str:
        """Where a delivered flow's sandbox starts: the tip once it holds
        HEAD, or HEAD while nothing waits."""
        self.follow()
        return self.tip() or self._git.get_current_commit()

    # ID: 2f8b6e1a-5c9d-4a72-b3e7-0d4a8f1c6b95
    def commit_from(
        self,
        worktree: GitService,
        base: str,
        paths: set[str] | None,
        message: str,
        *,
        author: tuple[str, str] | None = None,
    ) -> Delivered | None:
        """Commit the worktree's changes to ``paths`` (None: all of them) onto
        ``base`` and move the branch there. None when nothing changed.

        ``worktree`` is the flow's sandbox, checked out at ``base``; it shares
        the clone's object store, so its blobs are the clone's blobs. The
        branch moves only if it is still at ``base`` (or, with no branch yet,
        does not exist): a concurrent move raises instead of being lost.
        """
        changed = set(worktree.changed_paths("."))
        if paths is not None:
            changed &= set(paths)
        if not changed:
            return None
        present = sorted(p for p in changed if (Path(worktree.repo_path) / p).is_file())
        blobs = worktree.write_blobs(present)
        tree = self._git.tree_with(base, {p: blobs.get(p) for p in changed})
        sha = self._git.commit_tree(
            tree, [base], message, identity=autonomous_identity(), author=author
        )
        tip = self.tip()
        self._git.update_ref(DELIVERY_REF, sha, base if tip == base else None)
        logger.info(
            "DeliveryBranch: %s committed %d path(s) onto %s (HEAD unchanged)",
            sha[:12],
            len(changed),
            DELIVERY_BRANCH,
        )
        done = Delivered(parent=base, sha=sha, paths=sorted(changed))
        self.delivered.append(done)
        return done

    # ID: 9d4e7b2c-6a1f-4e85-a3c9-5f0b8d2e6a17
    def pending(self, target: str | None = None) -> tuple[int, list[str]]:
        """(commits, files) on the branch that ``target`` (default HEAD) lacks."""
        tip = self.tip()
        if tip is None:
            return 0, []
        target = target or self._git.get_current_commit()
        files = self._git.diff_names(target, tip)
        return (self._git.count_commits(target, tip) if files else 0), files

    # ID: 6b1c9f4e-8d2a-4b73-9e5f-2a7d0c3b8e41
    def pending_source(self, rel_path: str) -> str | None:
        """The branch's version of ``rel_path`` while it holds HEAD and differs
        from it — the tests that wait for delivery — else None."""
        tip = self.tip()
        head = self._git.get_current_commit()
        if tip is None or tip == head or not self._git.is_ancestor(head, tip):
            return None
        if rel_path not in self._git.diff_names(head, tip):
            return None
        data = self._git.committed_bytes(rel_path, DELIVERY_REF)
        return data.decode("utf-8", errors="replace") if data is not None else None


@dataclass(frozen=True)
# ID: a7e3c1d8-4f9b-4c62-8b5a-1e6d9f2c7a30
class DeliveryOutcome:
    """What one delivery cycle did.

    ``state``: ``none`` (nothing was ever delivered), ``nothing`` (no test
    waits), ``busy`` (the clone's lock was
    held), ``waiting`` (tests wait; ``reason`` says what is missing),
    ``current`` (already proposed), ``delivered`` (pushed and proposed),
    ``failed`` (``reason``).
    """

    state: str
    pending_commits: int = 0
    pending_files: int = 0
    pr_url: str | None = None
    reason: str | None = None
    dropped: list[str] = field(default_factory=list)


# ID: 3c8a5e2f-7b1d-4f96-a4e0-8d2c6b9f1e57
def github_token() -> str | None:
    """CORE_GITHUB_TOKEN, else the unit credential ``github-token``."""
    from shared.config import settings

    if settings.CORE_GITHUB_TOKEN:
        return settings.CORE_GITHUB_TOKEN
    creds = os.environ.get("CREDENTIALS_DIRECTORY")
    path = Path(creds) / "github-token" if creds else None
    if path and path.is_file():
        return path.read_text(encoding="utf-8").strip() or None
    return None


def _pr_body(commits: int, files: list[str]) -> str:
    shown = "\n".join(f"- `{p}`" for p in files[:_PR_FILE_LIST_MAX])
    more = len(files) - _PR_FILE_LIST_MAX
    return (
        "3. Tests written autonomously by CORE\n\n"
        "CORE's test generator (flow.build_test_for_symbol) wrote these tests; "
        "each one passed in a sandbox before it was committed here. "
        f"`{DELIVERY_BRANCH}` is CORE's own branch: CORE adds to it and merges "
        "main into it, and never checks it out.\n\n"
        f"Waiting: {commits} commit(s), {len(files)} file(s).\n\n"
        f"{shown}" + (f"\n- … and {more} more" if more > 0 else "") + "\n"
    )


# ID: 8e2b4d7a-1c6f-4a39-b5e8-7f0c3a9d2b64
async def deliver(
    delivery: DeliveryBranch,
    git: GitService,
    *,
    url: str | None,
    repo: str,
    base_branch: str,
    token: str | None,
    client: httpx.AsyncClient,
) -> DeliveryOutcome:
    """Push the branch and open or update its one pull request into main."""
    from body.services.thesis.github import GitHub, GitHubUnavailable

    commits, files = delivery.pending()
    if not files:
        return DeliveryOutcome("nothing")
    n_files = len(files)
    if not token or not url:
        missing = (
            "a GitHub token (CORE_GITHUB_TOKEN)" if not token else "CORE_UPSTREAM_URL"
        )
        return DeliveryOutcome("waiting", commits, n_files, reason=f"needs {missing}")
    tip = delivery.tip()
    if tip is not None and git.resolve_ref(PUSHED_REF) == tip:
        return DeliveryOutcome("current", commits, n_files)
    try:
        git.push_ref(url, DELIVERY_REF, DELIVERY_BRANCH, token)
    except RuntimeError as exc:
        return DeliveryOutcome("failed", commits, n_files, reason=f"push: {exc}"[:500])
    gh = GitHub(repo, token, client)
    owner = repo.split("/", 1)[0]
    body = _pr_body(commits, files)
    note = None
    try:
        open_pulls = await gh.get(
            f"pulls?state=open&base={base_branch}&head={owner}:{DELIVERY_BRANCH}"
        )
        if open_pulls:
            pull = await gh.send(
                "PATCH", f"pulls/{open_pulls[0]['number']}", {"body": body}
            )
        else:
            day = datetime.now(UTC).date().isoformat()
            pull = await gh.send(
                "POST",
                "pulls",
                {
                    "title": f"test: CORE-generated tests ({day})",
                    "body": body,
                    "head": DELIVERY_BRANCH,
                    "base": base_branch,
                },
            )
            try:
                # Like every PR into main, it merges itself once CI is green.
                await gh.graphql(
                    "mutation($id: ID!) { enablePullRequestAutoMerge("
                    "input: {pullRequestId: $id, mergeMethod: MERGE}) "
                    "{ clientMutationId } }",
                    {"id": pull.get("node_id")},
                )
            except GitHubUnavailable as exc:
                note = f"auto-merge not enabled: {exc}"[:300]
    except GitHubUnavailable as exc:
        return DeliveryOutcome(
            "failed", commits, n_files, reason=f"pull request: {exc}"[:500]
        )
    if tip is not None:
        git.update_ref(PUSHED_REF, tip, git.resolve_ref(PUSHED_REF))
    return DeliveryOutcome(
        "delivered", commits, n_files, pr_url=str(pull.get("html_url")), reason=note
    )


# ID: 5f9c2a6e-3d8b-4e71-a0b4-6c1e8d5f2a93
async def run_delivery(core_context: Any) -> DeliveryOutcome:
    """One cycle: merge main into the branch (under the clone's lock), then
    deliver it. Never raises: a failure is the outcome's ``failed`` state."""
    import asyncio

    import httpx

    from body.infrastructure.repo_sync import RepoBusy, repo_lock, upstream_branch
    from shared.config import settings

    git = core_context.git_service
    delivery = DeliveryBranch(git)
    try:
        if delivery.tip() is None:
            return DeliveryOutcome("none")

        def _follow() -> dict[str, Any]:
            with repo_lock(
                Path(git.repo_path), core_context.file_handler, blocking=False
            ):
                return delivery.follow()

        try:
            followed = await asyncio.to_thread(_follow)
        except RepoBusy:
            return DeliveryOutcome("busy")
        async with httpx.AsyncClient() as client:
            outcome = await deliver(
                delivery,
                git,
                url=settings.CORE_UPSTREAM_URL,
                repo=settings.CORE_GITHUB_REPO,
                base_branch=upstream_branch(),
                token=github_token(),
                client=client,
            )
    except Exception as exc:
        logger.warning("DeliveryBranch: cycle failed: %s", exc)
        return DeliveryOutcome("failed", reason=str(exc)[:500])
    if followed["dropped"]:
        return replace(outcome, dropped=followed["dropped"])
    return outcome
