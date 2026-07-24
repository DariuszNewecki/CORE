# src/shared/infrastructure/git_service.py

"""
GitService: thin, testable wrapper around git commands used by CORE.

Responsibilities
- Validate repo path and .git presence on init.
- Provide small, composable operations (status, add, commit, etc.).
- Raise RuntimeError with useful stderr/stdout on git failures.

Constitutional sanctuary: this module is the sole permitted user of
subprocess for git operations — both synchronous (_run_command) and
asynchronous (_run_async). All other layers must go through this service;
Will workers in particular must not spawn git subprocesses directly
(governance.dangerous_execution_primitives [r]).
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid
from datetime import date
from pathlib import Path

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)

_CFG_GIT = load_operational_config().git


# ID: b483a756-582b-4b64-b96c-f5936639f7ae
class StagingContaminationError(RuntimeError):
    """Raised by commit_paths when the staging area contains paths outside
    the declared production set (ADR-129 D1). Distinct from RuntimeError so
    callers can route D1 failures to mark_failed without catching all git
    errors (ADR-129 D7)."""


# ADR-071 D2.2 Phase 1: hermetic action execution via git worktree.
# Sandbox worktrees live under var/tmp/ (via PathResolver.tmp_dir) with names
# beginning SANDBOX_PREFIX so the orphan sweep on daemon boot can identify
# and reclaim them without touching unrelated worktrees.
# /tmp is prohibited per CLAUDE.md; all temp writes use var/tmp/.
SANDBOX_PREFIX = "core-action-sandbox-"

# ADR-155 D3: filename of the run-identity marker written inside a disposable
# demo run directory. marker_checked_remove() refuses to delete a directory
# whose marker is missing or whose content does not match the caller's run_id.
DEMO_RUN_MARKER_FILENAME = ".core-demo-run"


# ID: 4c70a9c7-ee57-40d7-80af-470c19223c21
class GitService:
    """Provides basic git operations for agents and services."""

    def __init__(self, repo_path: str | Path):
        """
        Initializes the GitService and validates the repository path.
        """
        self.repo_path = Path(repo_path).resolve()
        logger.info("GitService initialized for path %s", self.repo_path)

    def _run_command(self, command: list[str], cwd: Path | None = None) -> str:
        """Runs a git command and returns stdout; raises RuntimeError on failure."""
        try:
            effective_cwd = cwd or self.repo_path
            logger.debug(
                "Running git command: {' '.join(command)} in %s", effective_cwd
            )
            result = subprocess.run(
                ["git", *command],
                cwd=effective_cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            msg = e.stderr or e.stdout or ""
            logger.error("Git command failed: %s", msg)
            raise RuntimeError(f"Git command failed: {msg}") from e

    # ID: 06b9d4c8-a43e-4430-9f34-08d45747674a
    def init(self, path: Path):
        """Initializes a new Git repository at the specified path."""
        self._run_command(["init"], cwd=path)

    # ID: 82fee000-943a-45e9-a5d6-9d4894f16682
    def configure_local_identity(self, email: str, name: str) -> None:
        """Set a repo-local git author identity (ADR-155 D5).

        A disposable clone's commits must not depend on the operator's
        global ``~/.gitconfig`` — a child process re-rooted per D5 receives
        an explicit environment with no ``HOME`` inheritance, so global
        config is unreachable there, and a fresh "cold-room" host (D12/E15)
        may have no global identity configured at all. Setting it locally,
        scoped to this one repo, makes every commit inside the clone —
        whether authored from the parent process or the re-rooted child —
        independent of the host's own git configuration.
        """
        self._run_command(["config", "user.email", email])
        self._run_command(["config", "user.name", name])
        self._run_command(["config", "commit.gpgsign", "false"])

    # ID: cc819226-e33c-4559-a2d6-88d5d9e0ddaa
    def get_current_commit(self) -> str:
        """Returns the hash of the current HEAD commit."""
        return self._run_command(["rev-parse", "HEAD"])

    # ID: e7a5c19d-2f48-4b6c-9d3a-1f0b4e8c5d72
    def get_current_branch(self) -> str:
        """
        Returns the current branch name (e.g. 'main').

        Raises RuntimeError on failure — for example, when HEAD is detached
        or the repository has no commits yet. Callers that treat git
        metadata as optional should wrap this call.
        """
        return self._run_command(["rev-parse", "--abbrev-ref", "HEAD"])

    # ID: f8b6d2ae-3059-4c7d-ae4b-208c5f9d6e83
    def get_remote_url(self, remote: str = "origin") -> str:
        """
        Returns the configured URL for the given remote (default 'origin').

        Raises RuntimeError if the remote is not configured. Callers that
        treat the remote URL as optional should wrap this call.
        """
        return self._run_command(["remote", "get-url", remote])

    # ID: 62355f31-f9eb-4ac1-984e-eea556b29f31
    def get_staged_files(self) -> list[str]:
        """Returns a list of files that are currently staged for commit."""
        try:
            output = self._run_command(
                ["diff", "--cached", "--name-only", "--diff-filter=ACMR"]
            )
            if not output:
                return []
            return output.splitlines()
        except RuntimeError:
            return []

    # ID: ddc9fc71-b53c-4c91-bca1-8d36ebf1767c
    def write_tree(self) -> str:
        """Return the git object hash of the current index (``git write-tree``).

        Used by the isolated consequence-chain demo's before/after fingerprint
        (ADR-155 D2/D10) to detect any staged-but-uncommitted drift, distinct
        from ``get_current_commit()`` which only reflects committed HEAD.
        """
        return self._run_command(["write-tree"])

    # ID: f4de1b0d-a24e-4614-a0d4-52890bcc814b
    def list_tracked_files(self) -> list[str]:
        """Return every tracked file path (``git ls-files``).

        Used by the isolated consequence-chain demo's fingerprint (ADR-155
        D2/D10) to hash tracked working-tree content directly, catching
        unstaged modifications that ``write_tree()`` alone would miss.
        """
        output = self._run_command(["ls-files"])
        return output.splitlines() if output else []

    # ID: 7dbd1fed-8534-4bab-8323-5fd3ebe3caa7
    def list_untracked_files(self) -> list[str]:
        """Return untracked, non-ignored file paths (``git ls-files --others --exclude-standard``).

        Used by the isolated consequence-chain demo's fingerprint (ADR-155
        D2/D10 assertion 15) to prove pre-existing untracked bytes are
        unchanged after a run. Ignored paths (``.gitignore``) are excluded —
        the demo asserts nothing about runtime/build ephemera it never
        touched in the first place.
        """
        output = self._run_command(["ls-files", "--others", "--exclude-standard"])
        return output.splitlines() if output else []

    # ID: e506910f-2fc8-41ac-8f77-4dd79da1e6c6
    def is_git_repo(self) -> bool:
        """Returns True if a '.git' directory exists."""
        return (self.repo_path / ".git").exists()

    # ID: 1fdc163e-5305-462d-8fb2-7097172a1f40
    def is_committed(self, rel_path: str | Path) -> bool:
        """Return True if rel_path exists in the HEAD commit tree.

        Uses ``git ls-tree HEAD`` rather than ``ls-files`` so that staged-but-
        not-committed files return False — matching the set of files that would
        be present in a sandbox worktree created at HEAD (ADR-071 D2.2).
        """
        try:
            output = self._run_command(
                ["ls-tree", "--name-only", "HEAD", "--", str(rel_path)]
            )
            return bool(output.strip())
        except RuntimeError:
            return False

    # ID: 715fe14e-e905-4032-9721-35bc67639ed7
    def status_porcelain(self) -> str:
        """Return the porcelain status output with all untracked files listed
        individually (--untracked-files=all).

        The default git behaviour groups every file inside a brand-new directory
        under one ``?? dir/`` entry. That directory-level token never matches a
        file-level path in ``propagate_changes``'s ``only_paths`` allowlist,
        causing the intersection to be empty and nothing to propagate. Using
        ``--untracked-files=all`` forces file-level entries (e.g.
        ``?? tests/new_pkg/test_generated.py``) for all untracked content,
        including files in directories that are themselves new.
        """
        return self._run_command(["status", "--porcelain", "--untracked-files=all"])

    # ID: db520983-cdb8-4b99-a1d9-60467128b6dc
    def add_all(self) -> None:
        """Stages all changes, including untracked files.

        Intended for manual/CLI callers (governor-driven flows) that
        legitimately want to capture every working-tree change.
        Autonomous workers must NOT use this — they must use
        ``add(path)`` or ``commit_paths(paths, message)`` so their
        commits are scoped to declared files and cannot accidentally
        sweep in unrelated working-tree changes (debug edits, partial
        WIP, other workers' artifacts).
        """
        self._run_command(["add", "-A"])

    # ID: 823668c8-17fc-4472-9d37-b22735b8d018
    def add(self, path: str | Path) -> None:
        """Stages a specific file."""
        self._run_command(["add", str(path)])

    # ID: 3acb0e63-e71b-4eba-a5ed-88e8e4eec35d
    def commit(self, message: str) -> None:
        """
        Commits all changes with the provided message.

        Stages all changes (``git add -A``) before committing. If the first
        commit attempt fails because a pre-commit hook modified files (hooks
        exit non-zero and rewrite staged content), stages again and retries
        once. This is the standard two-pass pattern required when pre-commit
        hooks auto-fix files.

        Intended for manual/CLI callers (governor-driven flows) that
        legitimately want to capture every working-tree change in a single
        commit. Autonomous workers must NOT use this — they must use
        ``commit_paths(paths, message)`` so their commits are scoped to
        declared files and cannot accidentally sweep in unrelated
        working-tree changes (debug edits, partial WIP, other workers'
        artifacts).
        """
        self._run_command(["add", "-A"])
        try:
            self._run_command(["commit", "-m", message])
        except RuntimeError as first_err:
            # Pre-commit hooks can modify files and exit non-zero on the first
            # pass. Stage their changes and retry exactly once.
            logger.info(
                "GitService: first commit attempt failed — "
                "re-staging after pre-commit hook modifications and retrying: %s",
                first_err,
            )
            self._run_command(["add", "-A"])
            self._run_command(["commit", "-m", message])

    # ID: d4e5f6a7-b8c9-0123-4567-89abcdef0123
    def restore_paths(self, paths: list[str]) -> None:
        """
        Reverts the working-tree state of the given tracked paths to HEAD.

        Used by ProposalExecutor's failure branches per ADR-021 D2/D4.
        Untracked paths in the input are silently dropped (consistent with
        `git checkout -- <pathspec>` semantics).
        """
        if not paths:
            logger.debug("GitService.restore_paths: no paths to restore")
            return

        ls_output = self._run_command(["ls-files", "--", *paths])
        tracked = [line for line in ls_output.splitlines() if line]

        if not tracked:
            logger.info(
                "GitService.restore_paths: no tracked paths in input (count_input=%d)",
                len(paths),
            )
            return

        self._run_command(["checkout", "--", *tracked])
        logger.info("GitService.restore_paths: reverted %d paths", len(tracked))

    def _get_staged_paths(self) -> set[str]:
        """Return paths currently staged in the index (git diff --cached --name-only)."""
        output = self._run_command(["diff", "--cached", "--name-only"])
        return {line for line in output.splitlines() if line}

    # ID: e5f6a7b8-c9d0-1234-5678-9abcdef01234
    def commit_paths(self, paths: list[str], message: str) -> None:
        """
        Stages and commits exactly the given paths.

        Used by ProposalExecutor's success branches per ADR-021 D3. Mirrors
        the two-pass retry pattern in `commit` for pre-commit hook
        auto-modifications.

        ADR-129 D1: two-layer protection against staging contamination.

        Layer 1 — early check: before staging anything, verifies that the
        index contains no paths outside the production set. A concurrent
        session that has staged work would otherwise be swept into the
        autonomous commit, silently violating ADR-101 D1. The check raises
        rather than clears — clearing would destroy the session's staged
        work; raising makes the violation visible so the operator can commit
        or restore their staged changes before the next daemon cycle.

        Layer 2 — structural restriction: the commit command passes the
        production paths as a pathspec (``git commit -m msg -- p1 p2 …``).
        This tells git to commit only the staged changes for those specific
        paths, regardless of what else is in the index. Belt-and-suspenders:
        even if something slips into staging in the nanosecond window between
        the check and the ``git add``, the pathspec ensures only production
        bytes enter the commit object.
        """
        if not paths:
            raise ValueError(
                "commit_paths requires at least one path; an autonomous "
                "proposal that resolved to no files is malformed"
            )

        # ADR-129 D1 Layer 1: early contamination check.
        staged = self._get_staged_paths()
        production = set(paths)
        extra = staged - production
        if extra:
            extra_sample = sorted(extra)[:3]
            raise StagingContaminationError(
                f"ADR-129 D1: staging area has {len(extra)} path(s) outside "
                f"the declared production set — refusing autonomous commit to "
                f"prevent authorship contamination. Commit or restore staged "
                f"work first: {extra_sample}"
                f"{'...' if len(extra) > 3 else ''}"
            )

        # ADR-129 D1 Layer 2: pathspec-restricted commit.
        self._run_command(["add", "--", *paths])
        try:
            self._run_command(["commit", "-m", message, "--", *paths])
        except RuntimeError as first_err:
            logger.info(
                "GitService.commit_paths: first commit attempt failed — "
                "re-staging after pre-commit hook modifications and retrying: %s",
                first_err,
            )
            self._run_command(["add", "--", *paths])
            self._run_command(["commit", "-m", message, "--", *paths])

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567892
    def get_recent_commits(self, n: int = _CFG_GIT.recent_commits_n) -> list[str]:
        """
        Returns the last n commit summaries (oneline, no merges).
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            output = self._run_command(["log", f"-{n}", "--oneline", "--no-merges"])
            return output.splitlines() if output else []
        except RuntimeError:
            return []

    # ID: ff02b770-4928-4a10-9358-c6df84ff091f
    def get_diff_stat(self, base: str = "HEAD~5", target: str = "HEAD") -> str:
        """
        Returns the diffstat between two refs.
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            return self._run_command(["diff", "--stat", base, target])
        except RuntimeError:
            return ""

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789003
    def get_changed_files_log(self, n: int = _CFG_GIT.changed_files_log_n) -> list[str]:
        """
        Returns filenames touched in the last n commits (Python files only).
        Used by SystemContextGatherer for change context (Dimension 5).
        """
        try:
            output = self._run_command(
                ["log", "--name-only", "--pretty=format:", f"-{n}"]
            )
            return [
                line.strip()
                for line in output.splitlines()
                if line.strip() and line.strip().endswith(".py")
            ]
        except RuntimeError:
            return []

    # ID: 9f1e8c4a-5b73-4d29-a6f0-2c8e7b5d1a93
    def first_seen_date(self, rel_path: str) -> date | None:
        """Return the date the file at *rel_path* was first added to git, or None.

        Runs ``git log --diff-filter=A --format=%aI -- <rel_path>`` and parses
        the OLDEST author-date returned. git log outputs in reverse chrono
        order; the last line is the oldest matching commit, which for the
        --diff-filter=A filter is the original add (re-adds after deletion
        appear later in chrono and earlier in the output). Used by
        ROW4_NAMING coherence check (per ADR-073 D6 / topology §10.2) to
        derive the grandfather signal — artifacts whose first-seen date
        predates topology paper acceptance are permitted regardless of
        D-text naming coverage.

        Fail-soft: returns None on git error, missing file, unparseable date,
        or any other failure. The caller (ROW4_NAMING) treats "unknown
        first-seen" as ungrandfathered.
        """
        try:
            output = self._run_command(
                ["log", "--diff-filter=A", "--format=%aI", "--", rel_path]
            )
        except RuntimeError:
            return None
        lines = output.splitlines() if output else []
        if not lines:
            return None
        oldest = lines[-1]
        try:
            return date.fromisoformat(oldest[:10])
        except ValueError:
            return None

    # ID: 2204a851-0f11-495b-be3d-c0af82bb13ee
    def create_worktree(self, sha: str) -> ScopedGitService:
        """
        Create a hermetic git worktree rooted at `sha` for action execution.

        Path: SANDBOX_PARENT/SANDBOX_PREFIX<uuid4>/. Uses --detach so no
        branch is created. Returns a ScopedGitService wrapping the worktree;
        the caller MUST call cleanup() (or use as a context manager). Any
        leaked worktrees are reclaimed by sweep_orphan_worktrees() on the
        next daemon boot.

        ADR-071 D2.2 Phase 1.
        """
        sandbox_parent = PathResolver(self.repo_path).tmp_dir
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        worktree_path = sandbox_parent / f"{SANDBOX_PREFIX}{uuid.uuid4().hex}"
        self._run_command(["worktree", "add", "--detach", str(worktree_path), sha])
        logger.info(
            "GitService: created worktree %s at sha %s",
            worktree_path,
            sha[:12],
        )
        return ScopedGitService(worktree_path, parent=self)

    # ------------------------------------------------------------------
    # Async git operations — sanctuary for Will workers
    # ------------------------------------------------------------------

    async def _run_async(self, command: list[str]) -> tuple[int, str, str]:
        """Run a git command asynchronously. Returns (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *command,
            cwd=self.repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        assert proc.returncode is not None  # guaranteed after communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    # ID: 2ac7d7ba-e892-4858-b4ef-8f5f1c8094e5
    async def is_commit_on_branch(self, sha: str) -> bool:
        """Return True if sha is reachable from at least one branch.

        Runs ``git branch --contains <sha>``. A non-empty stdout means the
        commit is on a branch; empty stdout means it is orphaned.
        Used by CommitReachabilityAuditor (ADR-019 D1).
        """
        rc, stdout, _ = await self._run_async(["branch", "--contains", sha])
        return rc == 0 and bool(stdout.strip())

    # ID: 29e23c01-dd18-450b-b36a-1a0ac4ad5c24
    async def get_commit_meta(self, sha: str) -> dict[str, str]:
        """Return subject / author / date for a commit SHA.

        Runs ``git show -s --format=%s%n%an%n%cI <sha>``. Returns a sentinel
        subject when the object is no longer in the store (already gc'd).
        Used by CommitReachabilityAuditor to preserve orphan metadata before
        the object is pruned (#658).
        """
        rc, stdout, _ = await self._run_async(
            ["show", "-s", "--format=%s%n%an%n%cI", sha]
        )
        if rc != 0:
            return {"commit_subject": "<object not in store — gc'd before reconcile>"}
        lines = stdout.splitlines()
        return {
            "commit_subject": lines[0] if len(lines) > 0 else "",
            "commit_author": lines[1] if len(lines) > 1 else "",
            "commit_date": lines[2] if len(lines) > 2 else "",
        }

    # ID: 54c084b9-20ce-472e-abbf-45278c709d5b
    async def diff_file_names(self, pre_sha: str, post_sha: str) -> list[str] | None:
        """Return paths changed between two SHAs, or None on git failure.

        Runs ``git diff --name-only <pre_sha> <post_sha>``. Returns None
        rather than raising so callers can skip on failure without posting
        false-positive findings. Used by CommitAuthorshipAuditWorker
        (ADR-129 D4).
        """
        rc, stdout, stderr = await self._run_async(
            ["diff", "--name-only", pre_sha, post_sha]
        )
        if rc != 0:
            logger.warning(
                "GitService.diff_file_names: git diff failed for %s..%s: %s",
                pre_sha,
                post_sha,
                stderr.strip(),
            )
            return None
        return [f for f in stdout.strip().splitlines() if f]

    # ID: 7990798e-4c6b-4aff-a8ce-26f7f1f9d480
    def sweep_orphan_worktrees(self) -> int:
        """
        Remove any sandbox worktrees left behind by crashed actions.

        Lists worktrees registered against this repo, removes those whose
        path lives directly under SANDBOX_PARENT with the SANDBOX_PREFIX,
        and prunes the administrative entries. Returns the count removed.
        Safe to call on daemon boot; failures are logged and swallowed so
        ignition is never blocked.

        ADR-071 D2.2 Phase 1.
        """
        try:
            output = self._run_command(["worktree", "list", "--porcelain"])
        except RuntimeError as exc:
            logger.warning("GitService.sweep_orphan_worktrees: list failed: %s", exc)
            return 0

        sandbox_parent = PathResolver(self.repo_path).tmp_dir
        removed = 0
        for line in output.splitlines():
            if not line.startswith("worktree "):
                continue
            path_str = line[len("worktree ") :].strip()
            path = Path(path_str)
            if path.parent != sandbox_parent or not path.name.startswith(
                SANDBOX_PREFIX
            ):
                continue
            try:
                self._run_command(["worktree", "remove", "--force", path_str])
                removed += 1
                logger.info("GitService: removed orphan worktree %s", path_str)
            except RuntimeError as exc:
                logger.warning(
                    "GitService: failed to remove orphan worktree %s: %s",
                    path_str,
                    exc,
                )

        try:
            self._run_command(["worktree", "prune"])
        except RuntimeError as exc:
            logger.debug("GitService.sweep_orphan_worktrees: prune failed: %s", exc)

        return removed

    # ------------------------------------------------------------------
    # Isolated consequence-chain demo — disposable clone (ADR-155 D2/D3)
    # ------------------------------------------------------------------

    # ID: bc0e4718-eea3-45aa-a909-a19f1d691d77
    def create_disposable_clone(self, head_sha: str, dest: Path) -> GitService:
        """Create an isolated local clone of this repo at ``head_sha`` (ADR-155 D2).

        Uses ``git clone --no-hardlinks`` so the clone's object store is a
        physical copy — never hardlinks into this repo's ``.git/objects`` —
        because the clone must be able to outlive, and never write back
        into, the source repository's object database. Checks out exactly
        ``head_sha`` (detached) so the clone is pinned to the caller's
        captured baseline regardless of what the source's default branch
        points at, then removes the ``origin`` remote so the clone can
        never fetch from or push to the source. Returns a ``GitService``
        bound to the clone.
        """
        dest = Path(dest)
        self._run_command(["clone", "--no-hardlinks", str(self.repo_path), str(dest)])
        clone = GitService(dest)
        clone._run_command(["checkout", "--detach", head_sha])
        clone._run_command(["remote", "remove", "origin"])
        logger.info(
            "GitService: created disposable clone %s at %s (no remote)",
            dest,
            head_sha[:12],
        )
        return clone

    # ID: ecb6813c-e14f-4b1d-8829-d99af17e70c5
    def clone_has_no_remote(self) -> bool:
        """Return True if this repo has zero configured remotes (ADR-155 D2)."""
        output = self._run_command(["remote"])
        return output.strip() == ""

    @staticmethod
    # ID: 10333247-858b-452b-abd6-d0ac8ed1e882
    def marker_checked_resolve(path: Path, run_id: str, expected_root: Path) -> Path:
        """Validate that ``path`` is a legitimate, marker-confirmed disposable run
        directory and return its resolved location — **removing nothing** (ADR-155 D3).

        This is the guard half of :meth:`marker_checked_remove`, extracted so a
        caller can validate-and-preview (e.g. ``core-admin demo cleanup`` without
        ``--write``) using the *identical* checks that gate an actual removal.

        Refuses (raises ``ValueError``) unless every one of these holds:

        - ``run_id`` contains no wildcard or env-var-expansion characters
          (``$ % * ? [``) — defense in depth against an unresolved shell
          expansion reaching this call.
        - ``path`` exists and is not itself a symlink (no escape via a
          redirected directory).
        - ``path`` resolves to exactly ``expected_root/runs/<run_id>`` — not
          merely somewhere underneath it. This single equality check is what
          rejects a wrong parent, a root/``/`` target, and the source-repo
          path in one guard: none of those can ever equal that exact,
          deep, run-scoped path.
        - A marker file (``DEMO_RUN_MARKER_FILENAME``) exists directly
          inside ``path`` and its content is exactly ``run_id``.
        """
        if any(c in run_id for c in ("$", "%", "*", "?", "[")):
            raise ValueError(
                f"marker_checked cleanup refused: run_id contains an unsafe "
                f"character: {run_id!r}"
            )

        if not path.exists():
            raise ValueError(f"marker_checked cleanup refused: target does not exist: {path}")

        if path.is_symlink():
            raise ValueError(f"marker_checked cleanup refused: target is a symlink: {path}")

        resolved = path.resolve()
        expected = (expected_root.resolve() / "runs" / run_id).resolve()
        if resolved != expected:
            raise ValueError(
                f"marker_checked cleanup refused: {resolved} does not match the "
                f"expected run directory {expected}"
            )

        marker_path = resolved / DEMO_RUN_MARKER_FILENAME
        if not marker_path.is_file():
            raise ValueError(
                f"marker_checked cleanup refused: missing marker file at {marker_path}"
            )
        marker_content = marker_path.read_text(encoding="utf-8").strip()
        if marker_content != run_id:
            raise ValueError(
                f"marker_checked cleanup refused: marker content {marker_content!r} "
                f"does not match run_id {run_id!r}"
            )

        return resolved

    @staticmethod
    # ID: c88cd033-199e-4fd3-b857-4da0826c0b94
    def marker_checked_remove(path: Path, run_id: str, expected_root: Path) -> None:
        """Remove ``path`` only after :meth:`marker_checked_resolve` confirms it is a
        legitimate, marker-confirmed disposable run directory (ADR-155 D3).

        Delegates every guard to :meth:`marker_checked_resolve` (single source of
        the escape/marker/parent/root checks), then — and only then — calls
        ``shutil.rmtree`` on the single resolved path. No wildcards, no glob, no
        broad recursive target.
        """
        resolved = GitService.marker_checked_resolve(path, run_id, expected_root)
        shutil.rmtree(resolved)
        logger.info(
            "GitService.marker_checked_remove: removed %s (run_id=%s)", resolved, run_id
        )


# ID: ea3110a9-3a63-402f-af22-61f1860eff2b
class ScopedGitService(GitService):
    """GitService bound to a temporary git worktree (ADR-071 D2.2 Phase 1).

    Inherits every GitService operation; because `self.repo_path` points at
    the worktree, all commands execute against the sandbox rather than the
    main tree. The caller is responsible for `cleanup()` — either directly
    or via context-manager use — once execution finishes.
    """

    def __init__(self, worktree_path: Path, parent: GitService):
        super().__init__(worktree_path)
        self._parent = parent
        self._cleaned_up = False

    # ID: 375faa32-d545-47ee-9fdb-3894b425de5a
    def cleanup(self) -> None:
        """
        Remove the worktree. Idempotent. Uses `git worktree remove --force`
        which discards any uncommitted changes in the sandbox — intentional,
        because the caller is expected to copy out wanted changes before
        cleanup.
        """
        if self._cleaned_up:
            return
        try:
            self._parent._run_command(
                ["worktree", "remove", "--force", str(self.repo_path)]
            )
        except RuntimeError as exc:
            logger.warning(
                "ScopedGitService.cleanup: git worktree remove failed (%s); "
                "falling back to rmtree on %s",
                exc,
                self.repo_path,
            )
            if self.repo_path.exists():
                shutil.rmtree(self.repo_path, ignore_errors=True)
        finally:
            self._cleaned_up = True
            logger.info("ScopedGitService: cleaned up worktree %s", self.repo_path)

    def __enter__(self) -> ScopedGitService:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cleanup()
