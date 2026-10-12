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
  sparse checkout — **and** MIND/SPECS names a law root other than
  ``<REPO_PATH>/.intent`` / ``<REPO_PATH>/.specs`` → MIND / SPECS;
* otherwise → ``<root>/.intent`` / ``<root>/.specs`` (today's behaviour,
  and always right for an external target, which carries its own law).

In a development checkout MIND/SPECS are the repository's own — whether
discovered, or filled in from an explicit REPO_PATH — so both functions
return exactly what the old joins returned, for the checkout and for every
worktree inside it.
"""

from __future__ import annotations

from pathlib import Path


def _inside_configured_repo(root: Path) -> bool:
    from shared.config import settings

    repo = Path(settings.REPO_PATH).resolve()
    candidate = Path(root).resolve()
    return candidate == repo or repo in candidate.parents


def _beside(configured: Path, name: str) -> bool:
    """The law is kept beside the clone: the configured root is not the
    repository's own ``<REPO_PATH>/<name>``.

    Decided from the values, not from whether the setting was "explicit":
    an explicit REPO_PATH fills MIND/SPECS in from itself (config), which
    marks them set although nothing was moved.
    """
    from shared.config import settings

    own = Path(settings.REPO_PATH) / name
    return Path(configured).resolve() != own.resolve()


# ID: 94910383-e302-461d-82e4-d0d78ad3056e
def intent_root_for(repo_root: Path) -> Path:
    """The ``.intent`` root that governs ``repo_root``."""
    from shared.config import settings

    if _beside(settings.MIND, ".intent") and _inside_configured_repo(repo_root):
        return Path(settings.MIND)
    return Path(repo_root) / ".intent"


# ID: 0f3b7aad-5000-4aa1-b381-bd43749028f3
def specs_root_for(repo_root: Path) -> Path:
    """The ``.specs`` root that belongs to ``repo_root``."""
    from shared.config import settings

    if _beside(settings.SPECS, ".specs") and _inside_configured_repo(repo_root):
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
    """CORE's repository when none is passed.

    Discovery from the working directory first, exactly as
    ``resolve_default_repo_path`` (#544): the nearest ancestor holding a
    ``.intent/``. Only when none holds one -- a D2 service, whose working
    directory (/opt/core/run) and code-only clone carry no law -- does an
    explicit REPO_PATH decide, before the source-tree fallback. An explicit
    REPO_PATH naming an external target therefore does not displace CORE's
    own law for a process started inside CORE's checkout.
    """
    from shared.config import REPO_ROOT, discover_law_root, settings

    found = discover_law_root()
    if found is not None:
        return found
    if "REPO_PATH" in settings.model_fields_set:
        return Path(settings.REPO_PATH)
    return REPO_ROOT


# ID: 01eab0cd-f2c9-4768-b40c-bcbce556977a
def law_relpath(repo_root: Path, path: Path) -> str:
    """The repository-style name of ``path`` (``.intent/...``, ``.specs/...``,
    or relative to ``repo_root``) -- the inverse of ``law_path``.

    Under D2 the law is not inside the clone, so ``path.relative_to(repo_root)``
    raises for every law file; findings and reports still name them the way
    the repository does. A path outside all three is returned as given.
    """
    bases = (
        (".intent", intent_root_for(repo_root)),
        (".specs", specs_root_for(repo_root)),
        ("", Path(repo_root)),
    )
    for p in (Path(path), Path(path).resolve()):
        for name, root in bases:
            for base in (root, root.resolve()):
                if p.is_relative_to(base):
                    return Path(name, p.relative_to(base)).as_posix()
    return Path(path).as_posix()


# ID: 8ccc74df-f0c5-412a-bafc-8d86e4fa5693
def law_glob(repo_root: Path, pattern: str) -> list[Path]:
    """``repo_root.glob(pattern)`` for repository-style patterns that may name
    the law (``.intent/...``, ``.specs/...``), looked up where the law lives.

    Under D2 ``repo_root.glob(".specs/...")`` matches nothing: the clone carries
    no law, and an empty match reads as "nothing to check".
    """
    parts = Path(pattern).parts
    if parts and parts[0] in (".intent", ".specs") and len(parts) > 1:
        return list(law_path(repo_root, parts[0]).glob(str(Path(*parts[1:]))))
    return list(Path(repo_root).glob(pattern))
