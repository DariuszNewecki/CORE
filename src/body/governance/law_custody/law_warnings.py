# src/body/governance/law_custody/law_warnings.py
"""
The D5 warnings CORE computes for a law proposal (ADR-170 D5).

Computed from the bytes alone, old against new -- no repository code runs:
- a rule added or removed (``.intent/rules/**/*.json``);
- a rule's enforcement level changed, lowering marked as weakening;
- a ``scope.excludes`` entry added, or ``applies_to`` narrowed
  (``.intent/enforcement/mappings/**/*.yaml``);
- the constitutional core touched (always flagged);
- ``CLAUDE.md`` or ``.claude/`` changed: the assistant's own contract.

Meaning-level consequences cannot be computed; the proposer declares them
(``proposal.declared_warnings``), and ``law apply`` shows both lists.

CONSTITUTIONAL ALIGNMENT:
- Pure: inputs are bytes, output is a list. No I/O.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import yaml


_CONSTITUTIONAL_CORE = (
    ".intent/constitution/",
    ".intent/META/",
    ".intent/rules/governance/",
    ".intent/custody/",
)
_LEVELS = {"advisory": 0, "reporting": 1, "blocking": 2}


@dataclass(frozen=True)
# ID: ff1326c7-93f2-474f-86eb-05c3757f3ded
class LawWarning:
    """One computed warning. ``weakening`` marks a lowered enforcement level."""

    category: str
    path: str
    message: str
    weakening: bool = False

    # ID: e4f0d9f2-0d10-4885-90b9-780ef58af799
    def as_dict(self) -> dict[str, Any]:
        """JSON form, as recorded in the ledger line."""
        return {
            "category": self.category,
            "path": self.path,
            "message": self.message,
            "weakening": self.weakening,
        }


def _rules(data: bytes | None) -> dict[str, str]:
    """Map rule id -> enforcement level for a rules JSON document."""
    if data is None:
        return {}
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return {}
    rules = doc.get("rules") if isinstance(doc, dict) else None
    out: dict[str, str] = {}
    for rule in rules if isinstance(rules, list) else []:
        if isinstance(rule, dict) and isinstance(rule.get("id"), str):
            out[rule["id"]] = str(rule.get("enforcement", ""))
    return out


def _mapping_entries(node: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (rule id, mapping) for every dict that declares an ``engine``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict) and "engine" in value:
                yield str(key), value
            else:
                yield from _mapping_entries(value)


def _scopes(data: bytes | None) -> dict[str, tuple[set[str], set[str]]]:
    """Map rule id -> (applies_to, excludes) for an enforcement mapping."""
    if data is None:
        return {}
    try:
        doc = yaml.safe_load(data)
    except (yaml.YAMLError, UnicodeDecodeError):
        return {}
    out: dict[str, tuple[set[str], set[str]]] = {}
    for rule_id, mapping in _mapping_entries(doc):
        raw_scope = mapping.get("scope")
        scope: dict[str, Any] = raw_scope if isinstance(raw_scope, dict) else {}
        applies = scope.get("applies_to") or []
        excludes = scope.get("excludes") or []
        out[rule_id] = (
            {str(x) for x in applies} if isinstance(applies, list) else set(),
            {str(x) for x in excludes} if isinstance(excludes, list) else set(),
        )
    return out


def _rule_warnings(path: str, old: bytes | None, new: bytes | None) -> list[LawWarning]:
    before, after = _rules(old), _rules(new)
    found: list[LawWarning] = []
    for rule_id in sorted(after.keys() - before.keys()):
        found.append(
            LawWarning("rule_added", path, f"rule {rule_id} added ({after[rule_id]})")
        )
    for rule_id in sorted(before.keys() - after.keys()):
        found.append(
            LawWarning(
                "rule_removed",
                path,
                f"rule {rule_id} removed (was {before[rule_id]})",
                weakening=True,
            )
        )
    for rule_id in sorted(before.keys() & after.keys()):
        was, now = before[rule_id], after[rule_id]
        if was != now:
            lowered = _LEVELS.get(now, -1) < _LEVELS.get(was, -1)
            found.append(
                LawWarning(
                    "enforcement_changed",
                    path,
                    f"rule {rule_id}: {was} -> {now}"
                    + (" (WEAKENING)" if lowered else ""),
                    weakening=lowered,
                )
            )
    return found


def _scope_warnings(
    path: str, old: bytes | None, new: bytes | None
) -> list[LawWarning]:
    before, after = _scopes(old), _scopes(new)
    found: list[LawWarning] = []
    for rule_id in sorted(after):
        old_applies, old_excludes = before.get(rule_id, (set(), set()))
        new_applies, new_excludes = after[rule_id]
        for entry in sorted(new_excludes - old_excludes):
            found.append(
                LawWarning(
                    "exclude_added",
                    path,
                    f"{rule_id}: excludes gains {entry}",
                    weakening=True,
                )
            )
        if rule_id in before:
            for entry in sorted(old_applies - new_applies):
                found.append(
                    LawWarning(
                        "applies_to_narrowed",
                        path,
                        f"{rule_id}: applies_to loses {entry}",
                        weakening=True,
                    )
                )
    for rule_id in sorted(before.keys() - after.keys()):
        found.append(
            LawWarning(
                "mapping_removed",
                path,
                f"{rule_id}: enforcement mapping removed",
                weakening=True,
            )
        )
    return found


# ID: 40b31086-08ea-42a0-ad42-1d56aa0f181c
def compute_warnings(
    old: Mapping[str, bytes | None], new: Mapping[str, bytes | None]
) -> list[LawWarning]:
    """D5 warnings for every path in *new* (``None`` = removed / absent).

    *old* holds the current bytes of each path (``None`` when it does not
    exist yet). The constitutional core is listed first, then the
    assistant's contract, then rule and scope changes.
    """
    core: list[LawWarning] = []
    contract: list[LawWarning] = []
    changes: list[LawWarning] = []
    for path in sorted(new):
        before, after = old.get(path), new[path]
        if before == after:
            continue
        if path.startswith(_CONSTITUTIONAL_CORE):
            core.append(
                LawWarning("constitutional_core", path, "constitutional core changed")
            )
        if path == "CLAUDE.md" or path.startswith(".claude/"):
            contract.append(
                LawWarning(
                    "assistant_contract", path, "the assistant's own contract or hook"
                )
            )
        if path.startswith(".intent/rules/") and path.endswith(".json"):
            changes.extend(_rule_warnings(path, before, after))
        if path.startswith(".intent/enforcement/mappings/") and path.endswith(
            (".yaml", ".yml")
        ):
            changes.extend(_scope_warnings(path, before, after))
    return core + contract + changes
