# src/mind/logic/engines/cli_gate/checks/docs_no_phantom_commands.py

"""Verifies cli.docs_no_phantom_commands (ADR-167 D3): every command the docs
mention exists and is current.

A mention is ``core-admin <group> <command>`` or ``core <group> <command>``
inside an inline code span or a fenced code block; prose is not read, because
"core" is an ordinary word.

- ``core-admin`` mentions resolve against the live command tree; a mention of
  a hidden (deprecated) alias is a finding too.
- ``core`` mentions resolve against the headings of the committed
  ``docs/reference/core.md``, the inventory of the released core-cli. No
  import is needed, so this half never degrades; it relies on
  ``cli.reference_current`` keeping that page current.
- ``allow_mentions`` (mapping params) lists exact command strings exempt on
  purpose, e.g. migration notes naming removed commands.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from mind.logic.engines.cli_gate.checks.reference_current import (
    live_core_admin_tree,
)
from shared.cli.reference_markdown import CORE_CLI_PAGE, Command
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


_CHECK_ID = "cli_gate.docs_no_phantom_commands"
_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_MENTION = re.compile(r"(?<![\w-])(core-admin|core)(?![\w-])((?:\s+[a-z][a-z0-9-]*)+)")
_TOKEN = re.compile(r"[a-z][a-z0-9-]*")
_REFERENCE_HEADING = re.compile(r"^### `core ([^`]+)`")


@dataclass(frozen=True)
# ID: 146cd8a4-3b03-4b3c-8409-d6ba8af60e70
class CommandInventory:
    """Command paths of one CLI, as token tuples (``("project", "new")``)."""

    commands: frozenset[tuple[str, ...]]
    hidden: frozenset[tuple[str, ...]] = frozenset()

    @property
    # ID: defab6fc-930e-4ed9-aeb8-3d15ecbdcb97
    def groups(self) -> frozenset[tuple[str, ...]]:
        return frozenset(
            path[:i]
            for path in self.commands | self.hidden
            for i in range(1, len(path))
        )


# ID: 2338ff37-988d-4305-8857-23dd3454cb5c
def inventory_from_tree(root: Command) -> CommandInventory:
    """Visible and hidden command paths of a click command tree."""
    visible: set[tuple[str, ...]] = set()
    hidden: set[tuple[str, ...]] = set()

    def _walk(command: Command, path: tuple[str, ...], is_hidden: bool) -> None:
        is_hidden = is_hidden or bool(getattr(command, "hidden", False))
        subcommands = getattr(command, "commands", None)
        if isinstance(subcommands, dict):
            for name, sub in subcommands.items():
                _walk(sub, (*path, name), is_hidden)
        elif path:
            (hidden if is_hidden else visible).add(path)

    _walk(root, (), False)
    return CommandInventory(frozenset(visible), frozenset(hidden))


# ID: f17ab485-a011-4e0f-88b5-e672371e6b53
def inventory_from_reference(text: str) -> CommandInventory:
    """Command paths listed as ``### `core …``` headings in the core reference."""
    return CommandInventory(
        frozenset(
            tuple(match.group(1).split())
            for line in text.splitlines()
            if (match := _REFERENCE_HEADING.match(line))
        )
    )


# ID: 8c2ba9e8-d2f8-4584-a0e4-a5f5bbd6b516
def iter_code_mentions(text: str) -> Iterator[tuple[int, str, tuple[str, ...]]]:
    """Yield (line number, binary, tokens) for each mention inside code."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        snippets = (
            [line] if in_fence else [m.group(2) for m in _CODE_SPAN.finditer(line)]
        )
        for snippet in snippets:
            for match in _MENTION.finditer(snippet):
                tokens = tuple(_TOKEN.findall(match.group(2)))
                yield number, match.group(1), tokens


# ID: 1f9f8fe0-d5db-4369-b886-060712ec4faf
def resolve_mention(
    tokens: tuple[str, ...], inventory: CommandInventory
) -> tuple[str, tuple[str, ...]] | None:
    """None if the mention resolves to a live command (or a group, when the
    mention stops at one). Otherwise ``("phantom" | "hidden", path)`` for the
    shortest path that does not resolve or that names a hidden alias.
    """
    groups = inventory.groups
    for length in range(1, len(tokens) + 1):
        path = tokens[:length]
        if path in inventory.commands:
            return None
        if path in inventory.hidden:
            return ("hidden", path)
        if path not in groups:
            return ("phantom", path)
    return None


@dataclass(frozen=True)
class _Problem:
    file_path: str
    line: int
    kind: str
    mention: str


# ID: 5572497b-0c8c-4635-a0a7-e15b6da5fb03
def find_phantom_mentions(
    docs: dict[str, str],
    inventories: dict[str, CommandInventory],
    allow_mentions: frozenset[str] = frozenset(),
) -> list[_Problem]:
    """Problems across ``docs`` (repo-relative path -> text), in file order."""
    problems: list[_Problem] = []
    for file_path, text in docs.items():
        for line, binary, tokens in iter_code_mentions(text):
            outcome = resolve_mention(tokens, inventories[binary])
            if outcome is None:
                continue
            kind, path = outcome
            mention = " ".join((binary, *path))
            if mention in allow_mentions:
                continue
            problems.append(_Problem(file_path, line, kind, mention))
    return problems


# ID: 77c12806-ab09-4c04-8b2e-9e49d44bb4e7
class DocsNoPhantomCommandsCheck(CliCheck):
    check_type = "docs_no_phantom_commands"

    # ID: 4beca0df-4e86-48ca-a297-831098b278f0
    def __init__(
        self,
        path_resolver: PathResolver,
        core_admin_tree: Callable[[], Command] = live_core_admin_tree,
    ) -> None:
        self._path_resolver = path_resolver
        self._core_admin_tree = core_admin_tree

    def _docs(self, params: dict[str, Any]) -> dict[str, str]:
        repo_root: Path = self._path_resolver.repo_root
        # An excluded directory excludes everything under it (pathlib's
        # ``dir/**`` matches directories, not the files inside them).
        excluded: set[Path] = set()
        for pattern in params.get("exclude") or []:
            excluded.update(repo_root.glob(pattern))

        def _is_excluded(path: Path) -> bool:
            return path in excluded or any(
                parent in excluded for parent in path.parents
            )

        paths: set[Path] = set()
        for pattern in params.get("include") or []:
            paths.update(p for p in repo_root.glob(pattern) if not _is_excluded(p))
        for rel in params.get("extra_paths") or []:
            paths.add(repo_root / rel)
        return {
            p.relative_to(repo_root).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(paths)
            if p.is_file()
        }

    # ID: 80e06e50-143e-4d81-a182-18218547a52e
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        reference = self._path_resolver.repo_root / CORE_CLI_PAGE
        if not reference.is_file():
            return [
                AuditFinding(
                    check_id=_CHECK_ID,
                    severity=AuditSeverity.INFO,
                    message=(
                        f"`core` mentions were not checked: {CORE_CLI_PAGE} is missing. "
                        "Regenerate with `core-admin docs generate --write`."
                    ),
                    file_path=CORE_CLI_PAGE,
                )
            ]
        inventories = {
            "core-admin": inventory_from_tree(self._core_admin_tree()),
            "core": inventory_from_reference(reference.read_text(encoding="utf-8")),
        }
        problems = find_phantom_mentions(
            self._docs(params),
            inventories,
            frozenset(params.get("allow_mentions") or []),
        )
        return [
            AuditFinding(
                check_id=_CHECK_ID,
                severity=AuditSeverity.INFO,
                message=(
                    f"`{p.mention}` is a hidden (deprecated) alias; document the "
                    "current command."
                    if p.kind == "hidden"
                    else f"`{p.mention}` is not a command of the live CLI."
                ),
                file_path=p.file_path,
                line_number=p.line,
                context={"mention": p.mention, "kind": p.kind},
            )
            for p in problems
        ]
