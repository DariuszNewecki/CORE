# src/shared/infrastructure/intent/law_roots.py
"""
Where a repository's law lives (ADR-132 D10 · D2).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — resolves paths;
reads and writes nothing.

Today the law sits inside the repository (``<root>/.intent``,
``<root>/.specs``). Under D2 the services' clone is code only and the law is
kept beside it, custodian-owned, named by an explicit ``MIND`` / ``SPECS``
setting. Code that needs CORE's own law for a repository root asks here
instead of joining ``".intent"`` itself:

* the root is CORE's configured repository (``REPO_PATH``) or lies inside it
  — its sandbox worktrees live under ``var/tmp`` and inherit the clone's
  sparse checkout — **and** MIND/SPECS was set explicitly → MIND / SPECS;
* otherwise → ``<root>/.intent`` / ``<root>/.specs`` (today's behaviour,
  and always right for an external target, which carries its own law).

With MIND/SPECS not set explicitly — every development checkout today —
both functions return exactly what the old joins returned.
"""

from __future__ import annotations

from pathlib import Path


def _inside_configured_repo(root: Path) -> bool:
    from shared.config import settings

    repo = Path(settings.REPO_PATH).resolve()
    candidate = Path(root).resolve()
    return candidate == repo or repo in candidate.parents


# ID: 94910383-e302-461d-82e4-d0d78ad3056e
def intent_root_for(repo_root: Path) -> Path:
    """The ``.intent`` root that governs ``repo_root``."""
    from shared.config import settings

    if "MIND" in settings.model_fields_set and _inside_configured_repo(repo_root):
        return Path(settings.MIND)
    return Path(repo_root) / ".intent"


# ID: 0f3b7aad-5000-4aa1-b381-bd43749028f3
def specs_root_for(repo_root: Path) -> Path:
    """The ``.specs`` root that belongs to ``repo_root``."""
    from shared.config import settings

    if "SPECS" in settings.model_fields_set and _inside_configured_repo(repo_root):
        return Path(settings.SPECS)
    return Path(repo_root) / ".specs"


# ID: 595b7eb3-d8b7-4838-a03b-03bc0640e19d
def law_path(repo_root: Path, rel: str | Path) -> Path:
    """Resolve a repository-relative law path (``.intent/...``, ``.specs/...``)
    against the law that governs ``repo_root``; any other path joins the root."""
    parts = Path(rel).parts
    if parts and parts[0] == ".intent":
        return intent_root_for(repo_root).joinpath(*parts[1:])
    if parts and parts[0] == ".specs":
        return specs_root_for(repo_root).joinpath(*parts[1:])
    return Path(repo_root) / rel


# ID: c3851f8b-991d-4d27-9e86-65b7c02967b2
def configured_repo_root() -> Path:
    """CORE's repository when none is passed: an explicit REPO_PATH, else
    discovery from the working directory (resolve_default_repo_path, #544)."""
    from shared.config import resolve_default_repo_path, settings

    if "REPO_PATH" in settings.model_fields_set:
        return Path(settings.REPO_PATH)
    return resolve_default_repo_path()
