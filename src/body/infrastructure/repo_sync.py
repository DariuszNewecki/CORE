# src/body/infrastructure/repo_sync.py
"""
RepoSync — CORE's clone follows the upstream line (ADR-132 D10 · D2, C2).

Under D2 the services work in their own clone. Commits made elsewhere (the
governor, the assistant) reach it from the upstream URL — the branch merges
land on (``CORE_UPSTREAM_BRANCH``, default ``main``),
fetched over https, so nothing runs on the upstream's behalf — and only by
fast-forward:

* upstream contains HEAD      → fast-forward (journalled, see below);
* HEAD contains upstream      → nothing to do: CORE's own commits are ahead;
* the lines diverged          → refused, never merged; the caller posts a
  finding and keeps working on its current HEAD.

A checkout is not atomic: ``read-tree -m -u`` writes files and the index,
``update-ref`` moves HEAD last. So every sync writes a journal first
(``{from, to, added}``) and deletes it last. ``recover()`` runs at every service
process's start (``recover_at_boot``) and before every sync: with a journal present and HEAD still at ``from`` it
restores tracked files to HEAD and removes the journal's *added* paths that
are left untracked — only those, so runtime data under ``var/`` is never
swept. HEAD already at ``to`` means only the journal deletion was missed.
HEAD at neither is not a state this code made: it refuses (fail closed).

``repo_lock`` serialises the sync with the commit path in every process
(flock on a lock file under the run directory): a sync never fast-forwards
between a proposal's propagation and its commit.

Writes go through FileHandler; git through GitService (D1's safe options).
With no upstream configured, ``sync`` returns ``disabled`` and does nothing.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from shared.logger import getLogger
from shared.path_resolver import PathResolver


if TYPE_CHECKING:
    from body.infrastructure.storage.file_handler import FileHandler
    from shared.infrastructure.git_service import GitService


logger = getLogger(__name__)

SyncState = Literal[
    "disabled", "busy", "up_to_date", "fast_forwarded", "ahead", "diverged", "failed"
]

UPSTREAM_BRANCH = "main"
_JOURNAL_NAME = "repo-sync.json"
_LOCK_NAME = "repo-sync.lock"


# ID: 3bb70e98-4c10-4ace-8eb0-94ab21874efd
class SyncRecoveryRefused(RuntimeError):
    """A journal exists but HEAD is at neither end of it."""


@dataclass(frozen=True)
# ID: 37121464-c967-44d0-9c31-893f562b0207
class SyncOutcome:
    """What one sync did."""

    state: SyncState
    from_sha: str | None = None
    to_sha: str | None = None
    reason: str | None = None
    recovered: dict[str, object] | None = field(default=None)


def _rel(repo_root: Path, path: Path) -> str:
    return str(path.relative_to(repo_root))


# ID: d840c789-edea-4029-8891-1efe31737cc3
class RepoBusy(RuntimeError):
    """The clone's sync/commit lock is held by someone else."""


def _lock_path(repo_root: Path, file_handler: FileHandler) -> Path:
    lock_path = PathResolver.from_repo(repo_root).run_dir / _LOCK_NAME
    if not lock_path.exists():
        file_handler.write_runtime_text(_rel(repo_root, lock_path), "")
    return lock_path


@contextmanager
# ID: beed70a8-ff8f-406a-9f7c-7c94da3c207a
def repo_lock(
    repo_root: Path, file_handler: FileHandler, *, blocking: bool = True
) -> Iterator[None]:
    """Hold the clone's sync/commit lock for the duration of the block.

    ``blocking=False`` raises RepoBusy at once when the lock is held.
    """
    with _lock_path(repo_root, file_handler).open("r") as handle:
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(handle.fileno(), flags)
        except BlockingIOError as exc:
            raise RepoBusy("repository sync/commit lock is held") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@asynccontextmanager
# ID: 937112c8-4f56-4553-a65e-b23cfb6e2eb5
async def async_repo_lock(
    repo_root: Path,
    file_handler: FileHandler,
    *,
    timeout_sec: float = 600.0,
    poll_sec: float = 0.25,
) -> AsyncIterator[None]:
    """The same lock for async callers: polls without blocking the event
    loop; raises RepoBusy after ``timeout_sec``."""
    deadline = time.monotonic() + timeout_sec
    with _lock_path(repo_root, file_handler).open("r") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise RepoBusy(
                        f"repository sync/commit lock still held after {timeout_sec}s"
                    ) from exc
                await asyncio.sleep(poll_sec)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# ID: 9bbfd331-2479-40cc-ba84-3ddc7f791edd
def recover_at_boot(git: GitService, file_handler: FileHandler) -> dict | None:
    """Finish or undo an interrupted sync before this process reads the tree.

    Every service process (the daemon, each ``--only`` daemon, the API)
    calls this at start, before any worker or route can read a half-updated
    tree. It takes the lock blocking: a sync in flight in another process
    finishes first, and then there is nothing left to recover. With no
    journal it returns None without touching the lock. Raises
    SyncRecoveryRefused (fail closed) for a journal at neither end.
    """
    root = Path(git.repo_path)
    if not (PathResolver.from_repo(root).run_dir / _JOURNAL_NAME).exists():
        return None
    with repo_lock(root, file_handler):
        return RepoSync(git, file_handler, None).recover()


# ID: 37cf0713-0d78-4df9-92c2-10dc259b081d
def upstream_branch() -> str:
    """The branch CORE's clone follows (CORE_UPSTREAM_BRANCH, default main)."""
    from shared.config import settings

    return settings.CORE_UPSTREAM_BRANCH


# ID: b478d53f-3091-4f43-bfad-558c98b40d8f
def repo_sync_for(core_context: Any) -> RepoSync:
    """RepoSync for CORE's own clone, upstream from settings (inert if unset)."""
    from shared.config import settings

    return RepoSync(
        core_context.git_service,
        core_context.file_handler,
        settings.CORE_UPSTREAM_URL,
        upstream_branch(),
    )


# ID: a66cf739-20fd-40be-9155-6579103e1e25
class RepoSync:
    """Fast-forward-only sync of CORE's clone from the upstream URL."""

    def __init__(
        self,
        git: GitService,
        file_handler: FileHandler,
        upstream_url: str | None,
        branch: str = UPSTREAM_BRANCH,
    ) -> None:
        self._git = git
        self._fh = file_handler
        self._url = upstream_url or None
        self._branch = branch
        self._root = Path(git.repo_path)
        self._journal = PathResolver.from_repo(self._root).run_dir / _JOURNAL_NAME

    # ID: a6b74382-8b2d-486c-8cdd-f4b4a63343ec
    def recover(self) -> dict[str, object] | None:
        """Finish or undo an interrupted sync. None when there was none."""
        if not self._journal.exists():
            return None
        entry = json.loads(self._journal.read_text(encoding="utf-8"))
        from_sha, to_sha = entry["from"], entry["to"]
        head = self._git.get_current_commit()
        if head == to_sha:
            self._fh.remove_file(_rel(self._root, self._journal))
            return {"from": from_sha, "to": to_sha, "action": "completed"}
        if head != from_sha:
            raise SyncRecoveryRefused(
                f"sync journal says {from_sha[:8]}..{to_sha[:8]} but HEAD is "
                f"{head[:8]}; refusing to guess"
            )
        self._git.reset_hard_to_head()
        tracked = set(self._git.list_tracked_files())
        removed = []
        for rel in entry.get("added", []):
            if rel not in tracked and (self._root / rel).is_file():
                self._fh.remove_file(rel)
                removed.append(rel)
        self._fh.remove_file(_rel(self._root, self._journal))
        logger.warning(
            "RepoSync: interrupted sync %s..%s rolled back; removed %d added path(s)",
            from_sha[:8],
            to_sha[:8],
            len(removed),
        )
        return {
            "from": from_sha,
            "to": to_sha,
            "action": "rolled_back",
            "removed": removed,
        }

    # ID: e2bb76ea-75ca-4589-bd12-44583ef25818
    def sync(self, *, _after_step: Callable[[str], None] | None = None) -> SyncOutcome:
        """Fetch upstream and fast-forward when possible. Call under repo_lock.

        ``_after_step`` is a test-only fault-injection hook, called after
        each of "journal", "tree" and "ref".
        """
        if self._url is None:
            return SyncOutcome(state="disabled")
        step = _after_step or (lambda _name: None)
        try:
            recovered = self.recover()
            head = self._git.get_current_commit()
            upstream = self._git.fetch_branch(
                self._url, self._branch, f"refs/remotes/upstream/{self._branch}"
            )
        except SyncRecoveryRefused:
            raise
        except Exception as exc:
            logger.warning("RepoSync: fetch or recovery failed: %s", exc)
            return SyncOutcome(state="failed", reason=str(exc))

        if upstream == head:
            return SyncOutcome("up_to_date", head, upstream, recovered=recovered)
        if self._git.is_ancestor(upstream, head):
            return SyncOutcome("ahead", head, upstream, recovered=recovered)
        if not self._git.is_ancestor(head, upstream):
            return SyncOutcome(
                "diverged",
                head,
                upstream,
                reason="upstream and CORE's clone have diverged; not merging",
                recovered=recovered,
            )

        dirty = self._git.tracked_changes()
        if dirty:
            # Recovery resets tracked files to HEAD; never let it near
            # uncommitted work (e.g. a crashed proposal's propagated files).
            return SyncOutcome(
                "failed",
                head,
                upstream,
                reason=f"clone has {len(dirty)} uncommitted tracked change(s): {dirty[:5]}",
                recovered=recovered,
            )

        added = self._git.added_paths(head, upstream)
        self._fh.write_runtime_json(
            _rel(self._root, self._journal),
            {"from": head, "to": upstream, "added": added},
        )
        step("journal")
        try:
            self._git.read_tree_update(head, upstream)
            step("tree")
            self._git.move_head(upstream, head)
            step("ref")
        except Exception as exc:
            logger.warning("RepoSync: fast-forward interrupted: %s", exc)
            self.recover()
            return SyncOutcome("failed", head, upstream, reason=str(exc))
        self._fh.remove_file(_rel(self._root, self._journal))
        return SyncOutcome("fast_forwarded", head, upstream, recovered=recovered)

    # ID: 15da0087-385f-4451-8a31-835c918a98ea
    def sync_if_free(self) -> SyncOutcome:
        """Sync under the lock, or report ``busy`` at once when it is held
        (a proposal is between propagation and commit)."""
        if self._url is None:
            return SyncOutcome(state="disabled")
        try:
            with repo_lock(self._root, self._fh, blocking=False):
                return self.sync()
        except RepoBusy:
            return SyncOutcome(state="busy")
