# src/shared/infrastructure/intent/law_root_gate.py
"""
Startup law-root gate (ADR-132 D10 · D2, C1).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — reads the
configured law root and reports a verdict; it never writes and decides
nothing about the law's content.

A CORE service (the daemon, the API) must judge against the governed
repository's law. ``resolve_default_mind_path`` falls back to the bundled
machinery floor when no ``.intent/`` is found, which is right for a fresh
``core-admin`` install and wrong for a service: the floor carries no rules,
so every verdict would be vacuous. Under the D2 release runtime the
services run from a wheel with an empty working directory, which is exactly
when that fallback would fire. The gate refuses to start instead.

Refusing states: the law root does not exist; it has no ``rules/`` with at
least one rule file; it lies inside the installed package (the floor).
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)

EX_CONFIG = 78


# ID: f2062a25-51ae-49b4-a3a3-d92c261ccddc
class LawRootRefusal(RuntimeError):
    """The configured law root is not a governed repository's law."""

    exit_code = EX_CONFIG


# ID: fcb5e54e-4d38-4546-a099-8e90c0212d8a
def law_root_problem(mind: Path) -> str | None:
    """Return why ``mind`` cannot serve as a service's law root, or None."""
    if not mind.is_dir():
        return f"law root {mind} does not exist"
    package_root = Path(__file__).resolve().parents[2]
    try:
        mind.resolve().relative_to(package_root)
    except ValueError:
        pass
    else:
        return (
            f"law root {mind} lies inside the installed package "
            "(the machinery floor), which carries no rules"
        )
    rules = mind / "rules"
    if not rules.is_dir() or not any(p.is_file() for p in rules.rglob("*")):
        return f"law root {mind} has no rules under rules/"
    return None


# ID: 8174ae55-b506-4bf1-97bf-a6cb4abc41a8
def require_service_law_root(process: str, mind: Path) -> None:
    """Raise LawRootRefusal when ``mind`` is not usable; log the remedy."""
    problem = law_root_problem(mind)
    if problem is None:
        return
    message = (
        f"{process} refuses to start: {problem}. Set MIND (and REPO_PATH) to "
        "the governed repository's law, e.g. MIND=/opt/core/law/.intent."
    )
    logger.critical(message)
    raise LawRootRefusal(message)
