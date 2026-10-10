# src/shared/utils/patch_facts.py
"""What a unified diff does, read from its text alone.

Step 0 of the one flow (ADR-168 Amendment 2026-10-10; build plan U3): before
anyone approves a change, CORE states what the patch adds, modifies and
deletes, which top-level functions and classes it removes or introduces, and
whether the producer's claim of what it *retires* is true of the patch.

Pure: no filesystem, no git, no imports from the layers. A symbol is a
top-level ``def``/``async def``/``class`` (column 0); methods are not
symbols here. A symbol removed and re-added in the same file was changed,
not retired or introduced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_DIFF_GIT = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_TOP_LEVEL_DEF = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")


@dataclass
# ID: 715b79f6-b714-4389-a2c6-c50d342aa676
class PatchFacts:
    """Files and top-level symbols a patch touches."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    removed_symbols: dict[str, list[str]] = field(default_factory=dict)
    """Top-level symbols the patch removes and does not re-add, per file."""
    new_public_symbols: dict[str, list[str]] = field(default_factory=dict)
    """Top-level public symbols the patch adds that it did not remove, per file."""


# ID: 0fa7d654-46fe-42dc-affd-065b1571c75a
def read_patch(patch: str) -> PatchFacts:
    """Read a unified diff (``git diff`` format) into ``PatchFacts``."""
    facts = PatchFacts()
    removed: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    current: str | None = None
    status = "modified"

    def _close() -> None:
        if current is None:
            return
        {"added": facts.added, "modified": facts.modified, "deleted": facts.deleted}[
            status
        ].append(current)

    for line in patch.splitlines():
        header = _DIFF_GIT.match(line)
        if header:
            _close()
            current, status = header.group(2), "modified"
            continue
        if current is None:
            continue
        if line.startswith("new file mode"):
            status = "added"
        elif line.startswith("deleted file mode"):
            status = "deleted"
        elif line.startswith(("+++", "---")):
            continue
        elif line.startswith("-") and current.endswith(".py"):
            name = _symbol(line[1:])
            if name:
                removed.setdefault(current, []).append(name)
        elif line.startswith("+") and current.endswith(".py"):
            name = _symbol(line[1:])
            if name:
                added.setdefault(current, []).append(name)
    _close()

    for path in set(removed) | set(added):
        gone = set(removed.get(path, [])) - set(added.get(path, []))
        new = {
            n
            for n in set(added.get(path, [])) - set(removed.get(path, []))
            if not n.startswith("_")
        }
        if gone:
            facts.removed_symbols[path] = sorted(gone)
        if new:
            facts.new_public_symbols[path] = sorted(new)
    return facts


def _symbol(code_line: str) -> str | None:
    match = _TOP_LEVEL_DEF.match(code_line)
    return match.group(1) if match else None


# ID: d35cbaed-7750-49a4-a79c-7afc5175555c
def verify_retires(retires: list[str], facts: PatchFacts) -> list[dict[str, object]]:
    """Check each claimed retirement against the patch.

    An entry is a file (``path``: the patch must delete it) or a symbol
    (``path::Name``: the patch must remove that top-level symbol from that
    file without re-adding it there). Returns one row per entry:
    ``{"entry", "verified", "reason"}``.
    """
    rows: list[dict[str, object]] = []
    for entry in retires:
        path, sep, name = entry.partition("::")
        if sep:
            ok = name in facts.removed_symbols.get(path, [])
            reason = (
                "removed by the patch"
                if ok
                else f"the patch does not remove top-level symbol {name!r} from {path}"
            )
        else:
            ok = path in facts.deleted
            reason = (
                "deleted by the patch" if ok else f"the patch does not delete {path}"
            )
        rows.append({"entry": entry, "verified": ok, "reason": reason})
    return rows
