# src/body/self_healing/code_style_service.py

"""
Provides the service logic for formatting code according to constitutional style rules.

CONSTITUTIONAL FIX: Added 'write' parameter support to respect Dry Run intent.
Ensures that external tools (ruff format/ruff check) do not mutate the disk unless authorized.
"""

from __future__ import annotations

from pathlib import Path

from shared.utils.subprocess_utils import run_direct_command


# ID: 1655ba02-a26e-4f8b-847a-8e4d16acfea0
def format_code(
    path: str | None = None, write: bool = True, cwd: Path | str | None = None
) -> None:
    """
    Format code using ruff format and ruff check.

    Args:
        path: Optional specific target. Defaults to src and tests.
        write: If False, runs in check-only mode (Dry Run).
        cwd: Optional working directory for the ruff subprocess. Fix actions
            running inside a hermetic flow worktree (ADR-106) pass the scoped
            repo_path so ruff formats the sandbox tree rather than the real
            one (#638); None runs in the process cwd (CLI default).
    """
    if path is None:
        targets = ["src", "tests"]
    else:
        targets = [path]

    # --- Ruff Format Configuration ---
    ruff_format_args = ["format"]
    if not write:
        ruff_format_args.append("--check")
    ruff_format_args.extend(targets)

    # --- Ruff Check (Linter) Configuration ---
    ruff_check_args = ["check"]
    if write:
        ruff_check_args.extend(["--fix", "--unsafe-fixes"])
    else:
        # In dry-run, we just want to see what would happen
        pass
    ruff_check_args.extend(targets)

    # Execute. #660: ruff exits 1 to report findings (would-reformat in
    # --check mode, lint findings, or residual unfixable issues after --fix) and
    # reserves 2 for a genuine tool error. Both ruff steps are advisory to the
    # format action's purpose, so (0, 1) count as success; only exit 2+ raises.
    # Without this, every formattable file failed as "poetry command failed".
    #
    # Both phases run via run_direct_command, not run_poetry_command:
    # `poetry run ruff ...` requires Poetry to resolve a pyproject.toml
    # from cwd upward, which a cwd outside CORE's own tree (e.g. a
    # sandboxed worktree of an externally-bound governed target) need not
    # have. Poetry's own project-discovery failure exits 1 -- the same
    # code ruff itself uses for "would reformat" / lint findings -- so
    # allowed_returncodes=(0, 1) silently accepted a Poetry bootstrap
    # failure as a clean ruff pass. The format phase was corrected first
    # (ADR-159 Notes); the check/fix phase carried the identical latent
    # defect -- reporting complete success while never actually invoking
    # ruff -- until this correction. Resolving and launching ruff
    # directly for both phases removes Poetry from the path entirely, so
    # any exit code either phase returns unambiguously belongs to ruff.
    run_direct_command(
        f"✨ Ruff Format ({'Write' if write else 'Check'}): {' '.join(targets)}",
        "ruff",
        ruff_format_args,
        cwd=cwd,
        allowed_returncodes=(0, 1),
    )
    run_direct_command(
        f"✨ Ruff Check ({'Fix' if write else 'Check'}): {' '.join(targets)}",
        "ruff",
        ruff_check_args,
        cwd=cwd,
        allowed_returncodes=(0, 1),
    )
