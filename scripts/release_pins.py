#!/usr/bin/env python3
"""scripts/release_pins.py — keep the release pins equal to pyproject's version.

`pyproject.toml` `[project] version` is the one canonical version. Several
surfaces repeat it as a release pin (an image default, a badge, an example tag
to pin to). This script holds the list of those pins (PINS below) and two modes
that both read it:

  --check   (default; CI)  Read-only. Non-zero exit when any pin, or the
                           CHANGELOG comparison links, differ from the version.
  --write                  Rewrite the drifted pins and links in place. Only
                           deterministic substitutions; a pin whose line also
                           carries prose about the release is reported for a
                           hand edit, never half-rewritten.

Compatibility floors and minimums ("2.11.0 or later", a pack's
compatibility_floor) are statements about compatibility, not release pins, and
are deliberately absent from PINS.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = "CHANGELOG.md"
COMPARE = "https://github.com/DariuszNewecki/CORE/compare"


@dataclass(frozen=True)
class Pin:
    path: str
    # Group 1 is the version; the pattern must match exactly `count` times.
    pattern: str
    count: int = 1
    # False when the matched line also states what the release contains.
    writable: bool = True


V = r"(\d+\.\d+\.\d+)"
PINS: tuple[Pin, ...] = (
    Pin("Dockerfile", rf"^ARG CORE_RUNTIME_VERSION={V}$"),
    Pin("README.md", rf"badge/Release-v{V}-blue"),
    Pin("README.md", rf"^\*\*Current Release:\*\* v{V} ", writable=False),
    Pin("docs/cold-reviewer.md", rf"DariuszNewecki/CORE@v{V}\b"),
    Pin("docs/cold-reviewer.md", rf"\(`@v{V}` above\)"),
    Pin(".gitlab-ci/CORE.gitlab-ci.yml", rf'CORE_RUNTIME_VERSION: "{V}"'),
    Pin(".pre-commit-hooks.yaml", rf"rev: v{V}\b"),
)


def project_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def check_pin(pin: Pin, text: str, version: str) -> list[str]:
    """Problems with one pin in `text` (empty when it is current)."""
    matches = list(re.finditer(pin.pattern, text, flags=re.MULTILINE))
    if len(matches) != pin.count:
        return [
            f"{pin.path}: expected {pin.count} match(es) of {pin.pattern!r}, "
            f"found {len(matches)}"
        ]
    return [
        f"{pin.path}: pins {m.group(1)}, version is {version}"
        for m in matches
        if m.group(1) != version
    ]


def write_pin(pin: Pin, text: str, version: str) -> str:
    def repl(m: re.Match[str]) -> str:
        start, end = m.span(1)
        return m.group(0)[: start - m.start()] + version + m.group(0)[end - m.start() :]

    return re.sub(pin.pattern, repl, text, flags=re.MULTILINE)


def changelog_problems(text: str, version: str) -> list[str]:
    problems = []
    unreleased = re.search(rf"^\[Unreleased\]: {COMPARE}/v{V}\.\.\.HEAD$", text, re.M)
    if not unreleased:
        problems.append(f"{CHANGELOG}: no [Unreleased] comparison link")
    elif unreleased.group(1) != version:
        problems.append(
            f"{CHANGELOG}: [Unreleased] compares from v{unreleased.group(1)}, "
            f"version is {version}"
        )
    if not re.search(rf"^\[{re.escape(version)}\]: {COMPARE}/v", text, re.M):
        problems.append(f"{CHANGELOG}: no [{version}] comparison link")
    return problems


def write_changelog(text: str, version: str) -> str:
    """Point [Unreleased] at v{version} and add the [version] link if missing.

    The new [version] link compares from the version [Unreleased] compared
    from before, which is the previous release.
    """
    unreleased = re.search(rf"^\[Unreleased\]: {COMPARE}/v{V}\.\.\.HEAD$", text, re.M)
    if not unreleased:
        return text
    previous = unreleased.group(1)
    new_unreleased = f"[Unreleased]: {COMPARE}/v{version}...HEAD"
    lines = [new_unreleased]
    has_link = re.search(rf"^\[{re.escape(version)}\]: {COMPARE}/v", text, re.M)
    if not has_link and previous != version:
        lines.append(f"[{version}]: {COMPARE}/v{previous}...v{version}")
    return text[: unreleased.start()] + "\n".join(lines) + text[unreleased.end() :]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="read-only (default)")
    mode.add_argument("--write", action="store_true", help="rewrite drifted pins")
    args = parser.parse_args()

    version = project_version()
    problems: list[str] = []
    hand_edits: list[str] = []
    texts: dict[str, str] = {}

    def text_of(path: str) -> str:
        if path not in texts:
            texts[path] = (REPO_ROOT / path).read_text(encoding="utf-8")
        return texts[path]

    for pin in PINS:
        found = check_pin(pin, text_of(pin.path), version)
        problems += found
        if args.write and found:
            if pin.writable and not found[0].startswith(f"{pin.path}: expected"):
                texts[pin.path] = write_pin(pin, text_of(pin.path), version)
            else:
                hand_edits += found
    found = changelog_problems(text_of(CHANGELOG), version)
    problems += found
    if args.write and found:
        texts[CHANGELOG] = write_changelog(text_of(CHANGELOG), version)

    if not args.write:
        for problem in problems:
            print(f"DRIFT {problem}")
        if problems:
            print(
                f"release pins drift from pyproject version {version}; "
                "run scripts/release_pins.py --write"
            )
            return 1
        print(f"release pins match pyproject version {version}")
        return 0

    for path, text in texts.items():
        target = REPO_ROOT / path
        if target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
            print(f"wrote {path}")
    for problem in hand_edits:
        print(f"EDIT BY HAND {problem}")
    return 1 if hand_edits else 0


if __name__ == "__main__":
    sys.exit(main())
