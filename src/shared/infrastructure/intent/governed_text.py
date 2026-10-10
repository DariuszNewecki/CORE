# src/shared/infrastructure/intent/governed_text.py
"""
Loader for the governed-text paths in .intent/enforcement/config/governance_paths.yaml.

ADR-168 Amendment 2026-10-10 A5 / R5: a code proposal may not touch governed
text (``.intent/``, ``.specs/``, ``CLAUDE.md``, ...); governed text enters
only under ADR-170. The list is law, declared as data under
``governed_text.paths`` — this module only reads it.

An entry ending in "/" covers everything beneath it; any other entry is one
exact file. When the section is missing (e.g. a repository on the machinery
floor, which does not carry it) or unreadable, only ``.intent/`` is treated
as governed — the minimum every CORE repository has (proposal 0014).
"""

from __future__ import annotations

from collections.abc import Iterable

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)

_CONFIG_PATH = "enforcement/config/governance_paths.yaml"
_MINIMUM: tuple[str, ...] = (".intent/",)


# ID: d062d478-f546-45be-8e4f-340f25a5da77
def load_governed_text_paths() -> tuple[str, ...]:
    """Return the governed-text entries. Never raises."""
    try:
        import yaml

        raw = yaml.safe_load(get_intent_repository().load_text(_CONFIG_PATH))
        section = raw.get("governed_text") if isinstance(raw, dict) else None
        paths = section.get("paths") if isinstance(section, dict) else None
        if not isinstance(paths, list) or not paths:
            logger.warning(
                "governed_text: no governed_text.paths in %s -- treating only "
                ".intent/ as governed",
                _CONFIG_PATH,
            )
            return _MINIMUM
        return tuple(str(p) for p in paths if str(p).strip())
    except Exception as exc:
        logger.warning(
            "governed_text: failed to load (%s) -- treating only .intent/ as governed",
            exc,
        )
        return _MINIMUM


# ID: 00e767f8-c828-48b0-9a76-0c5661b5e8c4
def governed_paths_touched(paths: Iterable[str], governed: Iterable[str]) -> list[str]:
    """Return the repo-relative *paths* that fall under a *governed* entry."""
    entries = tuple(governed)
    hits: list[str] = []
    for path in paths:
        rel = path.removeprefix("./")
        for entry in entries:
            if entry.endswith("/"):
                if rel.startswith(entry) or rel == entry.rstrip("/"):
                    hits.append(path)
                    break
            elif rel == entry:
                hits.append(path)
                break
    return hits
