# src/features/introspection/discovery/loader.py

"""Refactored logic for src/features/introspection/discovery/loader.py."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def _iter_capability_files(base: Path) -> Iterable[Path]:
    if not base.exists():
        return []
    for p in sorted(base.glob("**/*")):
        if p.is_dir():
            continue
        if p.suffix.lower() in {".yaml", ".yml"}:
            yield p


def _extract_canonical_from_doc(doc: dict) -> set[str]:
    canonical: set[str] = set()
    tags = doc.get("tags", [])
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict) and isinstance(item.get("key"), str):
                canonical.add(item["key"])
    return canonical


def _extract_aliases_from_doc(doc: dict) -> dict[str, str]:
    aliases: dict[str, str] = {}
    raw = doc.get("aliases")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and k and v:
                aliases[k] = v
    return aliases


def _detect_alias_cycles(aliases: dict[str, str]) -> list[list[str]]:
    visited: set[str] = set()
    stack: set[str] = set()
    cycles: list[list[str]] = []

    # ID: d0cbfb51-a865-4552-ad69-a1b3953ff36d
    def dfs(node: str, path: list[str]):
        visited.add(node)
        stack.add(node)
        nxt = aliases.get(node)
        if nxt:
            if nxt not in visited:
                dfs(nxt, [*path, nxt])
            elif nxt in stack and nxt in path:
                idx = path.index(nxt)
                cycles.append([*path[idx:], nxt])
        stack.remove(node)

    for a in aliases:
        if a not in visited:
            dfs(a, [a])
    return cycles
