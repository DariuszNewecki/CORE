"""Review finding F10 (2026-10-23): the released engine is pinned.

The released-engine audit judges every pull request. Unpinned, it took the
latest core-runtime on PyPI, so any pushed ``v*`` tag changed the judge.
It installs one exact version, no newer than the repository's own.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _install_step() -> dict:
    jobs = yaml.safe_load((ROOT / ".github/workflows/core-ci.yml").read_text())["jobs"]
    (step,) = [
        s
        for s in jobs["released-engine-audit"]["steps"]
        if "core-runtime" in str(s.get("run", ""))
    ]
    return step


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def test_the_released_engine_is_one_exact_version() -> None:
    step = _install_step()
    pin = str(step["env"]["RELEASED_ENGINE"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", pin)
    assert '"core-runtime==$RELEASED_ENGINE"' in step["run"]


def test_the_pin_is_not_newer_than_the_repository() -> None:
    pin = str(_install_step()["env"]["RELEASED_ENGINE"])
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert _version(pin) <= _version(project["version"])
