# src/cli/logic/demo/seed.py
"""
Seed-file creation for the isolated consequence-chain demo (ADR-155 D7).

Writes exactly one file, deliberately missing its required `# ID:` symbol
anchor, into the disposable clone and commits it there — never into the
invoking repo (the parent orchestrator calls this against a `GitService`
already bound to the clone, per Phase 1's `create_isolated_clone`).

Uses ``FileHandler.write_runtime_bytes``, not ``write_runtime_text``,
specifically because ``write``'s text-content path auto-injects missing ID
anchors for ``repo-source`` paths (``_ensure_id_anchors``) — exactly the
violation this demo needs to seed, undoctored, for the real
``AuditViolationSensor`` to detect. ``write_runtime_bytes`` skips that
transform by design (its own docstring: "Bytes content skips source-shape
transforms... regardless of target class") while still routing through
FileHandler's path-governance guard (``_guard_paths``/IntentGuard) — an
existing, already-documented capability used for its documented purpose,
not a new bypass.
"""

from __future__ import annotations

from body.infrastructure.storage.file_handler import FileHandler
from shared.infrastructure.git_service import GitService


# ID: b1c777ae-df9c-4406-809c-c1fe1b74cf50
def seed_relative_path(run_id_short: str) -> str:
    """Return the D7 seed file's repo-relative path for this run."""
    return f"src/body/analyzers/demo_onramp_{run_id_short}.py"


# ID: 4c9a0d45-a7e1-4e48-a979-5c0c610aff9a
def seed_file_content(run_id_short: str) -> str:
    """Return the seed file's exact source — one public function, no ``# ID:`` anchor.

    ADR-155 D7: "The file contains one public function without its required
    stable ID anchor." Deliberately minimal — a module docstring, one import,
    one function — so the seeded violation is exactly the one condition
    ``linkage.assign_ids`` checks; nothing else in this file should be able
    to trip any other rule.
    """
    return (
        f'"""Isolated consequence-chain demo seed file (run {run_id_short}).\n\n'
        "Deliberately missing its required `# ID:` symbol anchor — this is\n"
        "the constitutional violation ADR-155's demo exists to detect,\n"
        "remediate, and prove resolved. Lives only in the disposable clone's\n"
        "git history, in one commit, never in the invoking repo.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n\n"
        f"def demo_onramp_marker_{run_id_short}() -> str:\n"
        '    """Return this run\'s marker string."""\n'
        f'    return "consequence-chain-demo::{run_id_short}"\n'
    )


# ID: 2e47eb6b-2f2f-4625-a23c-630fb9825472
def write_and_commit_seed(clone: GitService, run_id_short: str) -> str:
    """Write the seed file into the clone via FileHandler and commit it there.

    Returns the seed's repo-relative path. Uses ``GitService.commit_paths``
    (ADR-129 D1, pathspec-restricted) so the seed commit contains exactly
    the seed file — the D7 proof that only the seed file changed.
    """
    rel_path = seed_relative_path(run_id_short)
    content = seed_file_content(run_id_short)

    handler = FileHandler(str(clone.repo_path))
    handler.write_runtime_bytes(rel_path, content.encode("utf-8"))

    clone.commit_paths(
        [rel_path],
        f"seed: isolated consequence-chain demo run {run_id_short} (ADR-155 D7)",
    )
    return rel_path
