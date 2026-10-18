"""The README's command blocks must work when pasted as they are (proof run 3).

#1153: `pip install core-runtime` is refused outside a venv on current
Ubuntu/Debian (PEP 668), and the README never made one.
#1155: the "A new project" block ended DEGRADED (exit 1): no git init and no
commit, so the audit had no law of record. The existing-repo block had the
same gap.
"""

from __future__ import annotations

import re
from pathlib import Path


README = Path(__file__).resolve().parents[2] / "README.md"
_BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def _blocks(text: str) -> list[list[str]]:
    return [
        [ln.strip() for ln in b.splitlines() if ln.strip()]
        for b in _BASH_BLOCK.findall(text)
    ]


def _index(lines: list[str], needle: str) -> int:
    return next(i for i, ln in enumerate(lines) if needle in ln)


def _install_errors(text: str) -> list[str]:
    errors = []
    for lines in _blocks(text):
        if any("pip install core-runtime" in ln for ln in lines):
            pip = _index(lines, "pip install core-runtime")
            if not any("venv" in ln for ln in lines[:pip]):
                errors.append("pip install without a venv before it")
    return errors


def _commit_errors(text: str) -> list[str]:
    errors = []
    for lines in _blocks(text):
        if not any("adopt-pack" in ln for ln in lines):
            continue
        if not any("code audit" in ln for ln in lines):
            continue
        adopt, audit = _index(lines, "adopt-pack"), _index(lines, "code audit")
        if not any("git commit" in ln for ln in lines[adopt:audit]):
            errors.append(f"no git commit between adopt-pack and audit: {lines}")
        if any("project new" in ln for ln in lines):
            if not any(ln == "git init" for ln in lines[:adopt]):
                errors.append(f"project new without git init: {lines}")
    return errors


def test_install_block_creates_a_venv_before_pip() -> None:
    text = README.read_text(encoding="utf-8")
    assert any("pip install core-runtime" in ln for b in _blocks(text) for ln in b)
    assert _install_errors(text) == []


def test_every_adopt_then_audit_block_commits_the_law_first() -> None:
    text = README.read_text(encoding="utf-8")
    assert _commit_errors(text) == []
