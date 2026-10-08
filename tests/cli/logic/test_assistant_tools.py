"""ADR-168 D4.3: the assistant surface's allowlisted tools and their CLI face.

Three properties, on an adopter-shaped repository (bundled machinery floor,
one ADR, git) so they hold for a project other than CORE:

- **Allowlist (D3):** the tool set is exactly the pinned read and verdict
  operations; adding one is a deliberate change to this test.
- **Read-only (D3, acceptance check 3):** every tool runs with the database
  unreachable and leaves the repository byte-for-byte unchanged, so none can
  record governor authority.
- **Parity (D2 amendment):** each ``core-admin`` command prints exactly the
  answer the shared tool returns — the same call the MCP server makes.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.resources
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.logic.assistant_tools import TOOLS, ToolInputError, invoke
from shared.infrastructure.assistant_surface.law_facts import LawFacts


_ALLOWLIST = {
    "law_rule",
    "law_can_write",
    "decision_adr",
    "decision_adrs",
    "change_verdict",
}

# One call per tool, with the arguments each needs.
_CALLS = {
    "law_rule": {"rule_id": "governance.constitution.read_only"},
    "law_can_write": {"path": ".intent/rules/x.json"},
    "decision_adr": {"adr_id": "ADR-007"},
    "decision_adrs": {"status": "accepted"},
    "change_verdict": {},
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    shutil.copytree(
        Path(str(importlib.resources.files("shared._machinery_floor"))),
        root / ".intent",
        ignore=shutil.ignore_patterns("__pycache__", "__init__.py"),
    )
    adrs = root / ".specs" / "decisions"
    adrs.mkdir(parents=True)
    (adrs / "ADR-007-example.md").write_text(
        "---\nid: ADR-007\ntitle: 'ADR-007 — Example'\nstatus: accepted\n---\n\n"
        "### D1 — First decision\n",
        encoding="utf-8",
    )
    (root / "src").mkdir()
    (root / "src" / "ok.py").write_text('"""Ok."""\n', encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    # One uncommitted change, so the verdict has something in scope.
    (root / "src" / "new.py").write_text('"""New."""\n', encoding="utf-8")
    return root


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def test_the_tool_set_is_exactly_the_allowlist() -> None:
    assert set(TOOLS) == _ALLOWLIST
    assert set(_CALLS) == _ALLOWLIST
    for tool in TOOLS.values():
        assert tool.description
        assert tool.input_schema["type"] == "object"
        assert tool.input_schema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_unknown_tool_and_bad_arguments_are_refused(repo: Path) -> None:
    with pytest.raises(ToolInputError, match="No assistant tool"):
        await invoke("governor_approve", {}, repo)
    with pytest.raises(ToolInputError, match="rule_id"):
        await invoke("law_rule", {}, repo)
    with pytest.raises(ToolInputError, match="outside this repository"):
        await invoke("change_verdict", {"files": ["../../etc/passwd"]}, repo)


@pytest.mark.asyncio
async def test_law_tools_answer_exactly_what_the_shared_core_answers(
    repo: Path,
) -> None:
    facts = LawFacts(repo)
    assert (
        await invoke("law_rule", _CALLS["law_rule"], repo)
        == facts.rule("governance.constitution.read_only").as_dict()
    )
    assert (
        await invoke("law_can_write", _CALLS["law_can_write"], repo)
        == facts.can_write(".intent/rules/x.json").as_dict()
    )
    adr = await invoke("decision_adr", _CALLS["decision_adr"], repo)
    assert adr["class"] == "decision_history"
    assert adr["answer"]["decisions"] == ["D1 — First decision"]


@pytest.mark.asyncio
async def test_every_tool_is_read_only_and_needs_no_database(repo: Path) -> None:
    before = _tree_digest(repo)
    with patch(
        "shared.infrastructure.database.session_manager.get_session",
        side_effect=AssertionError("an assistant tool opened a database session"),
    ):
        for name, arguments in _CALLS.items():
            result = await invoke(name, arguments, repo)
            assert isinstance(result, dict), name
    assert _tree_digest(repo) == before

    verdict = await invoke("change_verdict", {}, repo)
    assert verdict["scope"]["files"] == ["src/new.py"]
    assert verdict["authoritative"] is False
    # The floor alone declares no project rules: nothing was judged.
    assert verdict["verdict"] == "NOT_EVALUATED"


_CLI = [
    (["law", "show", "governance.constitution.read_only"], "law_rule"),
    (["law", "check", ".intent/rules/x.json"], "law_can_write"),
    (["decisions", "show", "ADR-007"], "decision_adr"),
    (["decisions", "list", "--status", "accepted"], "decision_adrs"),
    # Exit 2: the floor alone declares no project rules (NOT_EVALUATED).
    (["code", "verify"], "change_verdict"),
]
_EXIT = {"change_verdict": 2}


@pytest.mark.parametrize(("argv", "tool"), _CLI)
def test_core_admin_prints_exactly_the_tool_answer(
    repo: Path, argv: list[str], tool: str
) -> None:
    """The real ``core-admin`` program, run in the adopter project the way a
    user or an assistant runs it: stdout is exactly the tool's JSON answer,
    and logging stays off stdout."""
    expected = asyncio.run(invoke(tool, _CALLS[tool], repo))

    done = subprocess.run(
        [sys.executable, "-m", "cli.admin_cli", *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert done.returncode == _EXIT.get(tool, 0), done.stderr[-2000:]
    assert json.loads(done.stdout) == expected
