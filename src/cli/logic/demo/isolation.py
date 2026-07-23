# src/cli/logic/demo/isolation.py
"""
Isolation-substrate orchestration for the isolated consequence-chain demo (ADR-155).

Phase 1 scope only: run identity, disposable clone creation + isolation
proof, invoking-repo before/after fingerprinting, disposable Compose
lifecycle, and marker-checked cleanup. No audit/proposal/execution/evidence
scenario (Phase 2) and no CLI command surface (Phase 3).

Every process spawn delegates to ``shared.utils.subprocess_utils``; every
git operation delegates to ``shared.infrastructure.git_service.GitService``.
This module's own direct filesystem writes are limited to the run-identity
marker and (via ``shutil.rmtree`` inside ``GitService.marker_checked_remove``,
not here) cleanup — both scoped to ``CORE_DEMO_STATE_DIR``, which is outside
every repo root and therefore outside ``FileHandler``'s repo-rooted write
gate. That is a deliberate, named exclusion — see the ADR-155 entries in
``.intent/enforcement/mappings/architecture/mutation_surface.yaml`` and
``governance_basics.yaml`` — not an unreviewed bypass.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

from cli.logic.demo.models import IsolationFingerprint, RunIdentity
from shared.exceptions import CoreError
from shared.infrastructure.git_service import DEMO_RUN_MARKER_FILENAME, GitService
from shared.logger import getLogger
from shared.utils.subprocess_utils import (
    SubprocessResult,
    compose_down_command,
    compose_up_command,
    run_compose_command,
)


logger = getLogger(__name__)

# ADR-155 §"Every substrate wait ... has a deadline" (Phase1-Map U15).
DEFAULT_COMPOSE_UP_TIMEOUT_SECONDS = 120.0
DEFAULT_COMPOSE_DOWN_TIMEOUT_SECONDS = 60.0


# ID: c9f990ed-b8dc-4533-b65a-70fb61b0ae64
class SubstrateTimeoutError(CoreError):
    """Raised when a substrate wait (compose up/down) exceeds its deadline (Phase1-Map U15)."""


# ID: 44c8fefe-63cb-43e3-9c1c-fd5ca561d320
def generate_run_identity(demo_state_dir: Path) -> RunIdentity:
    """Generate a fresh, opaque run identity and write its marker (ADR-155 D3).

    All of this run's disposable resources — the marker, the clone, and
    (once created) the Compose bookkeeping — live under
    ``demo_state_dir/runs/<run_id>/``, so ``cleanup_run`` can remove the
    entire run in one marker-checked ``shutil.rmtree``.
    """
    run_id = uuid.uuid4().hex
    state_dir = demo_state_dir / "runs" / run_id
    state_dir.mkdir(parents=True, exist_ok=False)
    marker_path = state_dir / DEMO_RUN_MARKER_FILENAME
    marker_path.write_text(run_id, encoding="utf-8")
    clone_dir = state_dir / "clone"
    logger.info("Demo: generated run identity %s at %s", run_id, state_dir)
    return RunIdentity(
        run_id=run_id, state_dir=state_dir, marker_path=marker_path, clone_dir=clone_dir
    )


# ID: 9593fa4b-e934-4b77-a9e3-b1ecdaa67d76
def hash_file(path: Path) -> str:
    """Return the sha256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ID: 0f54237f-9b32-423a-8989-602c80ac42c1
def hash_directory(path: Path) -> str:
    """Return a single sha256 hex digest over every file under ``path``.

    Hashes the sorted ``(relative_path, hash_file(...))`` pairs so the
    result is deterministic regardless of filesystem iteration order.
    Used to capture the clone's ``.intent/`` at clone time (ADR-155 D2/D10
    assertion 13) so a later mutation is detectable by comparison.
    """
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file_path.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(hash_file(file_path).encode("utf-8"))
    return digest.hexdigest()


# ID: 9f4d6631-6eb1-455b-8775-32f4e4b5234a
def create_isolated_clone(source: GitService, head_sha: str, identity: RunIdentity) -> GitService:
    """Create the disposable clone for this run at ``identity.clone_dir`` (ADR-155 D2)."""
    return source.create_disposable_clone(head_sha, identity.clone_dir)


# ID: 5b1b1d50-fcd1-452f-8814-981d0bca97a2
def prove_clone_isolation(clone: GitService, expected_head_sha: str) -> None:
    """Raise ``ValueError`` unless the clone is isolated: no remote, pinned HEAD (ADR-155 D2).

    Seed-path checks (that a Phase 2 seed commit didn't exist at baseline,
    that the seed commit is unreachable from the invoking repo) are deferred
    to Phase 2 — there is no scenario yet for them to check.
    """
    if not clone.clone_has_no_remote():
        raise ValueError(f"clone at {clone.repo_path} still has a remote configured")
    actual_head = clone.get_current_commit()
    if actual_head != expected_head_sha:
        raise ValueError(
            f"clone at {clone.repo_path} is pinned to {actual_head}, expected {expected_head_sha}"
        )


# ID: b8fae2ba-baaf-4571-81a2-f2c2c48dae3b
def capture_fingerprint(git: GitService) -> IsolationFingerprint:
    """Capture a byte-identity fingerprint of a repo's working tree (ADR-155 D2/D10).

    ``tracked_tree_sha`` hashes tracked files' actual on-disk content
    (catching unstaged working-tree modifications that ``write_tree()``
    alone — which only reflects the index — would miss). ``untracked_files``
    hashes every pre-existing, non-ignored untracked file so a later
    comparison can prove none of them were touched.
    """
    head_sha = git.get_current_commit()
    index_tree_sha = git.write_tree()

    tracked_digest = hashlib.sha256()
    for rel_path in sorted(git.list_tracked_files()):
        tracked_digest.update(rel_path.encode("utf-8"))
        tracked_digest.update(hash_file(git.repo_path / rel_path).encode("utf-8"))

    untracked_files = {
        rel_path: hash_file(git.repo_path / rel_path)
        for rel_path in git.list_untracked_files()
    }

    return IsolationFingerprint(
        head_sha=head_sha,
        index_tree_sha=index_tree_sha,
        tracked_tree_sha=tracked_digest.hexdigest(),
        untracked_files=untracked_files,
    )


async def _with_deadline(
    coro: asyncio.Future[SubprocessResult] | asyncio.Task[SubprocessResult],
    seconds: float,
    phase: str,
) -> SubprocessResult:
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except TimeoutError as exc:
        raise SubstrateTimeoutError(f"{phase} exceeded its {seconds}s deadline") from exc


# ID: 5102d54b-e869-4489-bace-07d13f2426b3
async def compose_up(
    project_name: str,
    compose_file: Path,
    env: dict[str, str],
    *,
    timeout_seconds: float = DEFAULT_COMPOSE_UP_TIMEOUT_SECONDS,
) -> SubprocessResult:
    """Bring up the disposable Compose project and wait for health (ADR-155 D4).

    ``compose up -d --wait`` blocks on Compose's own health checks; this
    wraps that wait in an explicit deadline so a stuck project fails loudly
    with a named phase rather than hanging the caller indefinitely.
    """
    args = compose_up_command(project_name, compose_file)
    coro = run_compose_command(args, cwd=compose_file.parent, env=env)
    return await _with_deadline(coro, timeout_seconds, phase="compose up")


# ID: 6e4e4722-b9af-414f-b299-d52de5bec784
async def compose_down(
    project_name: str,
    compose_file: Path,
    env: dict[str, str],
    *,
    timeout_seconds: float = DEFAULT_COMPOSE_DOWN_TIMEOUT_SECONDS,
) -> SubprocessResult:
    """Tear down the disposable Compose project, removing volumes (ADR-155 D4/D11)."""
    args = compose_down_command(project_name, compose_file)
    coro = run_compose_command(args, cwd=compose_file.parent, env=env)
    return await _with_deadline(coro, timeout_seconds, phase="compose down")


# ID: efb792bc-c0f5-4c8a-8c87-7257640acb2c
def cleanup_run(identity: RunIdentity, demo_state_dir: Path) -> None:
    """Remove the entire disposable run directory (ADR-155 D3/D11).

    Only valid once the run's Compose project has already been torn down —
    this removes filesystem state, not infrastructure. Delegates the actual
    removal to ``GitService.marker_checked_remove`` so the same
    escape/marker/parent/root guards protect every caller.
    """
    GitService.marker_checked_remove(identity.state_dir, identity.run_id, demo_state_dir)
    logger.info("Demo: cleaned up run %s", identity.run_id)
