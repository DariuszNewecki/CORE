# tests/mind/governance/test_mapping_excludes_target_real_paths.py
"""Every ``scope.excludes`` entry in an enforcement mapping must point at
something that exists (#857, #859, #860).

An exclude whose target has moved or been deleted is not inert: it silently
stops sanctioning the file it was written for (``file_handler.py`` moved
from ``src/shared/`` to ``src/body/`` and immediately acquired a live
``no_hardcoded_runtime_dirs`` finding), and it leaves the mapping reading
as if a decision still applied somewhere. Rules and their excludes are
governed data; drift in them is drift in the law.

The check is on the **fixed directory prefix** of each pattern — the path
components before the first one containing a wildcard — so a defensive
glob like ``src/mind/**/*_test.py`` passes as long as ``src/mind`` exists,
while ``src/will/cli_logic/**`` fails once ``src/will/cli_logic`` is gone.
A pattern whose only wildcard is in its last component (``…/commo*``) names
specific files and must additionally match at least one. Concrete paths
must exist outright. Read via the repository root, not via
``IntentRepository``: this is a test of the files on disk, the same surface
the loader reads.
"""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
MAPPINGS_ROOT = REPO_ROOT / ".intent" / "enforcement" / "mappings"


_WILDCARDS = ("*", "?", "[")


def _fixed_prefix(pattern: str) -> Path:
    """The directory components before the first wildcard-bearing one."""
    fixed: list[str] = []
    for component in pattern.split("/"):
        if any(w in component for w in _WILDCARDS):
            break
        fixed.append(component)
    return REPO_ROOT / "/".join(fixed)


def _is_stale(pattern: str) -> bool:
    if not _fixed_prefix(pattern).exists():
        return True
    components = pattern.split("/")
    last_only = any(w in components[-1] for w in _WILDCARDS) and not any(
        any(w in c for w in _WILDCARDS) for c in components[:-1]
    )
    if last_only and "**" not in components[-1]:
        # A file-name glob names specific files: it must match something.
        return not any(REPO_ROOT.glob(pattern))
    return False


def _excludes() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for mapping_file in sorted(MAPPINGS_ROOT.rglob("*.yaml")):
        doc = yaml.safe_load(mapping_file.read_text(encoding="utf-8")) or {}
        mappings = doc.get("mappings", doc)
        if not isinstance(mappings, dict):
            continue
        for rule_id, spec in mappings.items():
            if not isinstance(spec, dict):
                continue
            for pattern in (spec.get("scope") or {}).get("excludes") or []:
                if isinstance(pattern, str):
                    rel = str(mapping_file.relative_to(REPO_ROOT))
                    found.append((rel, str(rule_id), pattern))
    return found


# ID: 961efec6-d6b9-4607-a0a9-97081193ce07
def test_mapping_files_declare_excludes() -> None:
    """Guard for the guard: if the loader shape changes and nothing is found,
    the real test below would pass vacuously."""
    assert len(_excludes()) > 20


# ID: ea425b85-81d4-4c76-a6c8-5625a6ce0626
def test_every_exclude_has_an_existing_fixed_prefix() -> None:
    stale = [
        f"{rel}: {rule_id} excludes {pattern!r}"
        for rel, rule_id, pattern in _excludes()
        if _is_stale(pattern)
    ]
    assert not stale, (
        "stale scope.excludes (target moved or deleted — remove the entry, or "
        "retarget it under Path B if the file still exists elsewhere):\n  "
        + "\n  ".join(stale)
    )
