# src/cli/logic/project_scaffold.py
"""
`core-admin project new` — the Generate bootstrap stage (ADR-119 Amendment 2026-10-02, #892).

Creates a new repository that can host project law, and nothing more:

- the bundled machinery floor (``shared._machinery_floor``, ADR-108 D3) copied
  byte-for-byte into ``<target>/.intent/``, the same file selection and copy semantics
  ``project onboard`` uses (``byor._machinery_floor_files`` + ``shutil.copy2``);
- a minimal, neutral Python skeleton (``pyproject.toml``, ``README.md``,
  ``src/<package>/__init__.py``, ``tests/__init__.py``).

It creates no project-specific rules and makes no domain decisions. A freshly created
project is not auditable: ``code audit`` fails closed (ADR-108 D4) until rules are
authored or ratified, or a governance pack is explicitly adopted (ADR-119 D5, UR-08).

Operator surface (ADR-146 D3). Generate is a sibling of BYOR, not a BYOR path
(ADR-119 D1), so it lives here rather than in ``byor.py``; it reuses BYOR's floor
resolution and target-safety helpers as they are.

Writes go to an external target outside CORE's repository root, which ``FileHandler``
refuses (``architecture.execution_write.repository_containment``). This module is
therefore excluded by name from ``governance.mutation_surface.filehandler_required`` /
``governance.logic_mutation.governed`` — the same documented exception as ``byor.py``.
Nothing is ever git-added into CORE's repository.
"""

from __future__ import annotations

import keyword
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import typer

from cli.logic.byor import (
    _machinery_floor_files,
    _reject_unsafe_target,
    _resolve_machinery_floor,
)
from shared.logger import getLogger


logger = getLogger(__name__)

_INTENT_DIR = ".intent"
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
# ID: d453dbe7-2b39-40a9-99f7-49c972ae812a
class NewProjectPlan:
    """What `project new` would create: floor files to copy, skeleton files to write."""

    name: str
    package: str
    target_root: Path
    floor_copies: tuple[tuple[Path, str], ...]
    """(bundled source file, target-relative destination) — copied byte-for-byte."""
    skeleton_files: tuple[tuple[str, str], ...]
    """(target-relative destination, rendered text) — the only generated files."""

    @property
    # ID: f425789e-bff8-4f14-9ff2-a7be3b317c47
    def file_count(self) -> int:
        """Total number of files the plan delivers."""
        return len(self.floor_copies) + len(self.skeleton_files)


# ID: b52ae06a-d356-49af-997b-b91a0d82deaf
def plan_new_project(name: str, parent: Path, core_root: Path) -> NewProjectPlan:
    """Plan a new project at ``parent / name``. Pure: reads the bundled floor, writes nothing.

    Raises ``typer.Exit(1)`` for a name that is not a valid project/package name or
    when the bundled machinery floor cannot be found (a packaging error).
    """
    if not _NAME_PATTERN.match(name):
        logger.error(
            "Invalid project name %r: use letters, digits, '-' or '_', starting with a letter.",
            name,
        )
        raise typer.Exit(code=1)
    package = name.replace("-", "_").lower()
    if keyword.iskeyword(package):
        logger.error("Invalid project name %r: %r is a Python keyword.", name, package)
        raise typer.Exit(code=1)

    try:
        floor_dir = _resolve_machinery_floor(core_root)
    except RuntimeError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc

    floor_copies = tuple(
        (src, f"{_INTENT_DIR}/{src.relative_to(floor_dir).as_posix()}")
        for src in _machinery_floor_files(floor_dir)
    )
    skeleton_files = (
        ("pyproject.toml", _render_pyproject(name, package)),
        ("README.md", _render_readme(name)),
        (f"src/{package}/__init__.py", f'"""{name}."""\n'),
        ("tests/__init__.py", ""),
    )
    return NewProjectPlan(
        name=name,
        package=package,
        target_root=(parent / name).resolve(),
        floor_copies=floor_copies,
        skeleton_files=skeleton_files,
    )


# ID: f94ed88f-7e5d-4afc-8e8b-35340efaf035
def write_new_project(plan: NewProjectPlan, core_root: Path, write: bool) -> int:
    """Check the target and, with ``write=True``, deliver the plan. Returns the file count.

    Refuses (``typer.Exit(1)``), in dry-run as well as write mode, when the target
    overlaps CORE's own repository or is a system directory (BYOR's guard), when it
    exists as a file, or when it exists as a non-empty directory. Never overwrites.
    """
    target = plan.target_root
    _reject_unsafe_target(target, core_root.resolve())
    if target.exists():
        if not target.is_dir():
            logger.error(
                "Refusing target %s: it exists and is not a directory.", target
            )
            raise typer.Exit(code=1)
        if any(target.iterdir()):
            logger.error(
                "Refusing target %s: directory exists and is not empty. "
                "project new never overwrites; choose another name or --path.",
                target,
            )
            raise typer.Exit(code=1)

    if not write:
        return plan.file_count

    try:
        for src, rel in plan.floor_copies:
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        for rel, text in plan.skeleton_files:
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
    except OSError as exc:
        logger.error("Could not write the new project at %s: %s", target, exc)
        raise typer.Exit(code=1) from exc

    missing = [
        rel
        for rel in (
            *(r for _, r in plan.floor_copies),
            *(r for r, _ in plan.skeleton_files),
        )
        if not (target / rel).is_file()
    ]
    if missing:
        logger.error(
            "Delivery incomplete at %s; missing: %s", target, ", ".join(missing)
        )
        raise typer.Exit(code=1)
    return plan.file_count


def _render_pyproject(name: str, package: str) -> str:
    return (
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        'description = ""\n'
        'readme = "README.md"\n'
        'requires-python = ">=3.12"\n'
        "dependencies = []\n"
        "\n"
        "[build-system]\n"
        'requires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.build_meta"\n'
        "\n"
        "[tool.setuptools.packages.find]\n"
        'where = ["src"]\n'
        f'include = ["{package}*"]\n'
    )


def _render_readme(name: str) -> str:
    return (
        f"# {name}\n"
        "\n"
        "Bootstrapped by CORE (`core-admin project new`).\n"
        "\n"
        "This repository contains CORE's machinery floor in `.intent/`: the schemas,\n"
        "taxonomies and enforcement configuration that can host project law. It contains\n"
        "**no project-specific law yet**. Until rules are authored or ratified, or a\n"
        "governance pack is explicitly adopted, `core-admin code audit` fails closed.\n"
        "That is intended: CORE does not choose this project's law.\n"
    )
