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


_READ_TOOLS = {
    "law_rule",
    "law_can_write",
    "decision_adr",
    "decision_adrs",
    "change_verdict",
}
# ADR-168 Amendment 2026-10-10 A1: the one write — submitting a change.
_SUBMIT_TOOLS = {"validate_change", "submit_change"}
_ALLOWLIST = _READ_TOOLS | _SUBMIT_TOOLS

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
    assert set(_CALLS) == _READ_TOOLS
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


# ── ADR-168 D3: the submit tools never reach governor authority ─────────────


def _fake_api(run_status: str = "completed", ok: bool = True):
    calls: list[tuple[str, str]] = []

    async def _request(self, method: str, path: str, **kwargs):
        calls.append((method, path))
        if path.startswith("/v1/fix/run/"):
            return {"run_id": "r1", "status": "pending"}
        if path.startswith("/v1/fix/runs/"):
            return {
                "status": run_status,
                "result": {
                    "ok": ok,
                    "data": {"validation_results": {"full_audit": ok}},
                },
            }
        return {"proposal_id": "p1", "status": "pending", "json": kwargs.get("json")}

    return calls, _request


_SUBMIT_ARGS = {
    "patch": "diff",
    "validation_run_id": "r1",
    "goal": "g",
    "anchor_kind": "governor_request",
    "anchor_refs": ["the decided prompt"],
    "producer": "claude-opus",
}


# ID: a998301b-ade8-4223-b978-b89c4a208c28
@pytest.mark.asyncio
async def test_submit_tools_call_only_their_listed_routes(repo: Path) -> None:
    from unittest.mock import patch

    from cli.logic.assistant_tools import _SUBMIT_ROUTES

    calls, fake = _fake_api()
    with patch("api.cli.client.CoreApiClient._request", fake):
        validated = await invoke("validate_change", {"patch": "diff"}, repo)
        submitted = await invoke("submit_change", _SUBMIT_ARGS, repo)

    assert validated["validation_run_id"] == "r1"
    assert submitted["submitted"] is True
    for method, path in calls:
        assert any(
            method == m and path.startswith(prefix) for m, prefix in _SUBMIT_ROUTES
        ), (method, path)
        assert not any(word in path for word in ("approve", "reject", "execute"))
    # The producer carries the account that actually ran the tool.
    sent = submitted["json"]
    assert sent["producer"].startswith("claude-opus (account: ")


# ID: b84dc32b-53c5-4fc9-9905-62a286c3bf08
@pytest.mark.asyncio
async def test_submit_change_submits_nothing_for_a_failed_or_running_check(
    repo: Path,
) -> None:
    from unittest.mock import patch

    for status, ok in (("failed", False), ("completed", False), ("running", True)):
        calls, fake = _fake_api(run_status=status, ok=ok)
        with patch("api.cli.client.CoreApiClient._request", fake):
            out = await invoke("submit_change", _SUBMIT_ARGS, repo)
        assert out["submitted"] is False
        assert ("POST", "/v1/proposals/submit") not in calls


# ID: c61aaa7b-0d7e-4b67-a954-4f6e9f5e3b82
def test_the_submit_path_never_writes_governor_authority() -> None:
    """D3 enumeration, CORE side: the code behind POST /v1/proposals/submit
    calls no approve/reject/execute and sets no approver or authority."""
    import ast

    # The authority writers: the state manager (approve/reject/mark_*), the
    # executors, and the approver fields. Database reads (session.execute)
    # are not authority and are not matched.
    forbidden_names = {"ProposalStateManager", "ProposalExecutor", "ActionExecutor"}
    forbidden_calls = {
        "approve",
        "reject",
        "mark_executing",
        "mark_finalizing",
        "mark_completed",
        "mark_failed",
    }
    forbidden_keywords = {"approved_by", "approval_authority", "approved_at"}
    modules = [
        "src/will/autonomy/producer_submission.py",
        "src/will/autonomy/step_zero.py",
        "src/will/autonomy/proposal_factory.py",
        "src/body/services/validated_candidate_service.py",
        "src/cli/logic/assistant_tools.py",
    ]
    root = Path(__file__).resolve().parents[3]
    for rel in modules:
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls, (rel, node.func.attr)
            if isinstance(node, ast.keyword):
                assert node.arg not in forbidden_keywords, (rel, node.arg)
            if isinstance(node, ast.Name):
                assert node.id not in forbidden_names, (rel, node.id)
            if isinstance(node, ast.alias):
                assert node.name.rpartition(".")[2] not in forbidden_names, (
                    rel,
                    node.name,
                )


# ID: 7b649075-d071-421a-9d4e-879186c5f553
@pytest.mark.asyncio
async def test_the_patch_reaches_core_byte_for_byte(repo: Path) -> None:
    """Stripping the patch dropped its final newline; git apply then called it
    corrupt (found by the first real submission, U8)."""
    from unittest.mock import patch

    sent: list[dict] = []

    async def _request(self, method: str, path: str, **kwargs):
        sent.append(kwargs.get("json") or {})
        if path.startswith("/v1/fix/runs/"):
            return {"status": "completed", "result": {"ok": True, "data": {}}}
        return {"run_id": "r1", "status": "pending"}

    diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    with patch("api.cli.client.CoreApiClient._request", _request):
        await invoke("validate_change", {"patch": diff}, repo)
        await invoke("submit_change", {**_SUBMIT_ARGS, "patch": diff}, repo)

    assert sent[0]["params"]["patch"] == diff
    assert sent[-1]["patch"] == diff
