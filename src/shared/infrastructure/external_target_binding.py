# src/shared/infrastructure/external_target_binding.py

"""
Fail-closed validation for binding one CORE process, one external Git
repository, and one isolated database together (Governor ruling
2026-09-05, recorded in .specs/decisions/ADR-159-autonomy-thesis-
acceptance-boundary.md Notes; part of the Governor-authorized
external-target safety package).

This module answers exactly one question: "is it safe to treat *target*
as the one external repository this process is bound to?" It performs
no side effects of its own — no filesystem writes, no database
connections, no Git mutations, no construction of GitService/CoreContext,
and — this is the load-bearing property — it never imports or calls
``get_intent_repository()``, directly or transitively. A future
external-run CLI command is expected to call
:func:`validate_external_target_binding` before constructing anything
else, exactly once, with the raw REPO_PATH / MIND / DATABASE_URL values
it read from the process environment.

Why this module does not use GitService: ``shared.infrastructure.
git_service`` loads ``shared.infrastructure.intent.operational_config``
at import time, which calls ``get_intent_repository()`` as a
module-level side effect. Importing GitService here — even lazily,
inside a function body — would initialize the global IntentRepository
singleton the moment this guard is *invoked*, defeating the guard's own
purpose (the singleton must not exist yet when this check runs). This is
the dependency-cycle case that justifies a small, independent git
top-level lookup here rather than reuse of GitService's subprocess
sanctuary. The lookup below is read-only (``git rev-parse
--show-toplevel``) and does not construct anything Git-mutating.

Deliberately NOT a target-context abstraction: there is no class here
holding repo_root/intent_root/envelope state. Every check is a plain
function over explicit inputs; nothing is cached, and nothing here reads
``os.environ`` itself — the caller reads the environment and passes the
raw values in, so tests never depend on the developer's actual process
environment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.exceptions import CoreError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 28c7cc14-d765-42db-aa4a-97d1ba95ad28
class ExternalTargetBindingError(CoreError):
    """A candidate external-target binding fails one required invariant.

    The message names exactly which invariant failed and is always safe
    to log or display: it never includes ``database_url_value`` or any
    other secret-bearing input, only path/identity information.
    """


def _git_toplevel(path: Path) -> str | None:
    """Return ``git rev-parse --show-toplevel`` for *path*, or None on failure.

    Deliberately independent of GitService (see module docstring) — this
    is the one narrow, read-only, non-GitService git invocation in the
    codebase, justified by the dependency cycle GitService's import-time
    IntentRepository access would otherwise create. Never raises; a
    missing/unreachable ``git`` binary or a non-repository path both
    resolve to None, which the caller treats as a refusal.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def _resolve_existing(label: str, raw: str | Path) -> Path:
    """Resolve *raw* to an existing, symlink-canonicalized Path or refuse.

    Centralizes the "does this exist, and what is its real path"
    check used for every path input below, so every comparison in this
    module compares canonical paths — the mechanism that satisfies the
    "no relevant paths escape through symlink resolution" requirement.
    """
    try:
        return Path(raw).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExternalTargetBindingError(
            f"{label} does not resolve to an existing path: {raw}"
        ) from exc


# ID: 55d5332d-5e16-4e17-b583-1d131759b24a
def validate_external_target_binding(
    target: Path,
    *,
    repo_path_value: str | None,
    mind_value: str | None,
    database_url_value: str | None,
    core_repo_root: Path,
) -> Path:
    """Validate a proposed one-process/one-database/one-target binding.

    Raises :class:`ExternalTargetBindingError` on the first invariant
    that fails to hold; returns the canonical (symlink-resolved) target
    path only when every invariant holds. Performs no side effects:
    it does not create ``.intent/``, does not initialize or rebind
    ``get_intent_repository()``, does not connect to any database, does
    not mutate Git state, and does not write evidence.

    Args:
        target: The operator-selected candidate external repository.
            Never inferred from the current working directory — the
            caller must supply it explicitly.
        repo_path_value: The raw ``REPO_PATH`` value the caller read
            from the process environment (``None`` if unset). Must be
            explicitly supplied and must resolve to exactly *target*.
        mind_value: The raw ``MIND`` value the caller read from the
            process environment (``None`` if unset). Must be explicitly
            supplied and must resolve to exactly ``<target>/.intent``.
        database_url_value: The raw ``DATABASE_URL`` value the caller
            read from the process environment (``None`` if unset). Must
            be explicitly supplied and non-empty; its value is never
            included in any error message or log line.
        core_repo_root: CORE's own repository root, supplied explicitly
            so this function never reads ``shared.config.settings`` and
            remains fully injectable in tests.

    Returns:
        The canonical, symlink-resolved target path.

    Raises:
        ExternalTargetBindingError: on any violated invariant. The
            message identifies which invariant failed; it never
            contains ``database_url_value``.
    """
    resolved_target = _resolve_existing("target", target)
    if not resolved_target.is_dir():
        raise ExternalTargetBindingError(
            f"target is not a directory: {resolved_target}"
        )

    git_marker = resolved_target / ".git"
    if not git_marker.exists():
        raise ExternalTargetBindingError(
            f"no .git found at target (expected a directory or worktree "
            f"file at {git_marker})"
        )

    toplevel_raw = _git_toplevel(resolved_target)
    if toplevel_raw is None:
        raise ExternalTargetBindingError(
            f"git could not resolve a top-level repository at "
            f"{resolved_target} (not a git repository, or git is unavailable)"
        )
    resolved_toplevel = _resolve_existing("git top-level", toplevel_raw)
    if resolved_toplevel != resolved_target:
        raise ExternalTargetBindingError(
            f"target ({resolved_target}) is not the git top-level repository "
            f"— git resolved the top-level as {resolved_toplevel}. Refusing "
            f"to bind a subdirectory of another repository as an external "
            f"target."
        )

    intent_dir = resolved_target / ".intent"
    if not intent_dir.is_dir():
        raise ExternalTargetBindingError(
            f"no .intent/ directory found at target: {intent_dir}"
        )
    resolved_intent_dir = _resolve_existing("target .intent/", intent_dir)

    if not repo_path_value:
        raise ExternalTargetBindingError(
            "REPO_PATH was not explicitly supplied for external mode"
        )
    resolved_repo_path = _resolve_existing("REPO_PATH", repo_path_value)
    if resolved_repo_path != resolved_target:
        raise ExternalTargetBindingError(
            f"REPO_PATH ({resolved_repo_path}) does not match the canonical "
            f"target ({resolved_target})"
        )

    if not mind_value:
        raise ExternalTargetBindingError(
            "MIND was not explicitly supplied for external mode"
        )
    resolved_mind = _resolve_existing("MIND", mind_value)
    if resolved_mind != resolved_intent_dir:
        raise ExternalTargetBindingError(
            f"MIND ({resolved_mind}) does not match the target's .intent/ "
            f"({resolved_intent_dir})"
        )

    if not database_url_value:
        raise ExternalTargetBindingError(
            "DATABASE_URL was not explicitly supplied for external mode"
        )

    resolved_core_root = _resolve_existing("CORE repository root", core_repo_root)
    if resolved_target == resolved_core_root:
        raise ExternalTargetBindingError(
            "target is CORE's own repository root; refusing to bind external mode to it"
        )
    if resolved_core_root in resolved_target.parents:
        raise ExternalTargetBindingError(
            f"target ({resolved_target}) is located beneath CORE's own "
            f"repository root ({resolved_core_root}); refusing to bind "
            f"external mode to a path inside CORE's own checkout"
        )

    logger.info("external_target_binding: validated binding to %s", resolved_target)
    return resolved_target
