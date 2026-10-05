# src/shared/infrastructure/code_identity.py

"""Loaded-code identity: is this process running the code on disk? (ADR-169 D3 / ADR-030).

The daemon does not reload Python modules. ADR-030 decided that when the code
on disk differs from the code a daemon process loaded, the process DEGRADEs and
suspends autonomous execution until the governor restarts it.

The identity is the same fingerprint the ADR-169 state ledger records:

    law_digest(git blob ids of every file under src/)  — tracked and untracked,
    honouring .gitignore, computed with ``git hash-object`` (no objects written)

``capture_loaded_code_identity`` runs once at process boot (main daemon and every
``--only`` process): at that moment the code on disk is the code the process
loads. ``code_drift`` compares it with ``src/`` on disk now.

States:
- ``inactive`` — nothing was captured: this process is not a daemon (a CLI run
  or a test loads code fresh). The gate does not apply.
- ``match`` — the loaded code is the code on disk.
- ``stale`` — they differ (any ``src/`` change, committed or not — ADR-030).
- ``unknown`` — capture or the comparison failed. Never treated as ``match``:
  a precondition that cannot be evaluated must not pass
  (governance.no_governance_bypass), so acting workers stay suspended.

Read-only: runs git through GitService, writes nothing. Process-global state is
deliberate — the identity belongs to the process, not to any one worker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared.infrastructure.git_service import GitService
from shared.infrastructure.intent.law_state import law_digest
from shared.logger import getLogger


logger = getLogger(__name__)

CodeDriftState = Literal["inactive", "match", "stale", "unknown"]

# The code under this pathspec is what a daemon process imports.
CODE_PATHSPEC = "src"

# Re-hashing src/ is cheap (~1.2k blobs) but every acting worker asks each
# cycle; a short cache keeps that to one git call per process per window.
_CACHE_TTL_SEC = 60.0


@dataclass(frozen=True)
# ID: ce9a5a20-5ce2-4ff1-8179-84839097306d
class CodeDrift:
    """This process's loaded code vs the code on disk now."""

    state: CodeDriftState
    loaded_identity: str | None = None
    disk_identity: str | None = None
    reason: str | None = None

    @property
    # ID: 938d79e7-8973-4ea4-ad54-3c0866593d50
    def suspends_autonomy(self) -> bool:
        """True when acting workers in this process must not act (ADR-030)."""
        return self.state in ("stale", "unknown")


class _ProcessIdentity:
    """Process-global holder: what was loaded, and the last comparison."""

    captured: bool = False
    git: GitService | None = None
    loaded_identity: str | None = None
    capture_error: str | None = None
    cached: CodeDrift | None = None
    cached_at: float = 0.0


# ID: a4565618-26b4-4edf-bc9f-da52e70b663d
def compute_code_identity(git: GitService) -> str:
    """Fingerprint ``src/`` as it is on disk now. Raises RuntimeError on git failure."""
    return law_digest(git.hash_working_paths(CODE_PATHSPEC))


# ID: 98563385-2461-49a1-9282-25bcffc20008
def capture_loaded_code_identity(repo_root: Path) -> str | None:
    """Record the identity of the code this process is loading. Call once at boot.

    Returns the identity, or None when it could not be computed — in which
    case the process is ``unknown`` from then on (fail closed, not inactive).
    """
    _ProcessIdentity.captured = True
    _ProcessIdentity.cached = None
    try:
        git = GitService(repo_root)
        _ProcessIdentity.git = git
        _ProcessIdentity.loaded_identity = compute_code_identity(git)
        _ProcessIdentity.capture_error = None
    except Exception as exc:
        _ProcessIdentity.loaded_identity = None
        _ProcessIdentity.capture_error = str(exc)
        logger.warning("loaded code identity could not be captured: %s", exc)
    return _ProcessIdentity.loaded_identity


# ID: 477c8263-ad80-401b-b6c1-0d2e19899a9c
def loaded_code_identity() -> str | None:
    """The identity captured at boot, or None (not captured / capture failed)."""
    return _ProcessIdentity.loaded_identity


# ID: c720b514-fb12-43f2-8571-9fffad2f3f4a
def code_drift(*, use_cache: bool = True) -> CodeDrift:
    """Compare this process's loaded code with ``src/`` on disk now."""
    if not _ProcessIdentity.captured:
        return CodeDrift(state="inactive")
    now = time.monotonic()
    cached = _ProcessIdentity.cached
    if (
        use_cache
        and cached is not None
        and now - _ProcessIdentity.cached_at < _CACHE_TTL_SEC
    ):
        return cached

    loaded = _ProcessIdentity.loaded_identity
    git = _ProcessIdentity.git
    if loaded is None or git is None:
        drift = CodeDrift(
            state="unknown",
            reason=f"loaded code identity was not captured: {_ProcessIdentity.capture_error}",
        )
    else:
        try:
            disk = compute_code_identity(git)
            drift = CodeDrift(
                state="match" if disk == loaded else "stale",
                loaded_identity=loaded,
                disk_identity=disk,
            )
        except Exception as exc:
            drift = CodeDrift(
                state="unknown",
                loaded_identity=loaded,
                reason=f"code on disk could not be fingerprinted: {exc}",
            )
    _ProcessIdentity.cached = drift
    _ProcessIdentity.cached_at = now
    return drift


# ID: 89f6ec6d-17a8-4d94-b36d-35bb604c24bd
def reset_process_identity() -> None:
    """Forget the captured identity (tests; a process never un-captures)."""
    _ProcessIdentity.captured = False
    _ProcessIdentity.git = None
    _ProcessIdentity.loaded_identity = None
    _ProcessIdentity.capture_error = None
    _ProcessIdentity.cached = None
    _ProcessIdentity.cached_at = 0.0
