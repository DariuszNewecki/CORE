"""The `.claude/hooks` CORE verdict check (ADR-168 D4.1).

A real git repository stands in for the development checkout; its
`.venv/bin/core-admin` is a stand-in for `core-admin code verify` (the
change_verdict tool) that records where it ran and how it was called, and
says BLOCKED when the judged tree holds a file named BLOCK. The hook must
pass anything but `git commit`, run the per-file change check -- not the
full audit, which stays in CI -- on the tree each commit lands in (with
REPO_PATH and PYTHONPATH naming it) in every spelling of `git commit` the
shared detector knows, and refuse (fail closed) on BLOCKED, NOT_EVALUATED, a
check that produced no verdict, or a payload it cannot read.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
# The source of the copy installed in .claude/hooks/ (core-law, not in git).
HOOK = REPO / "infra" / "claude-hooks" / "core-verdict.sh"

FAKE_AUDIT = """#!/bin/sh
printf '%s|%s|%s\\n' "$(pwd)" "$REPO_PATH" "$PYTHONPATH" >>"$FAKE_AUDIT_RECORD"
[ "$*" = "code verify" ] || { echo "called as: $*" >&2; exit 9; }
[ -e CRASH ] && exit 3
if [ -e UNJUDGED ]; then
  echo '{"verdict": "NOT_EVALUATED", "blocking": [], "error": "no rules"}'
  exit 2
fi
if [ -e BLOCK ]; then
  echo '{"verdict": "BLOCKED", "scope": {"files": ["BLOCK"]}, "blocking": [{"rule_id": "fake.rule", "file": "BLOCK", "line": 1, "message": "blocked"}]}'
  exit 1
fi
echo '{"verdict": "CLEAR_IN_SCOPE", "scope": {"files": ["a.py", "b.py"]}, "blocking": []}'
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def dev(tmp_path: Path) -> Path:
    dev = tmp_path / "dev"
    dev.mkdir()
    _git(dev, "init", "-q")
    (dev / "base").write_text("base")
    # A CORE tree (src/cli/admin_cli.py) runs its own code: PYTHONPATH=<tree>/src.
    (dev / "src" / "cli").mkdir(parents=True)
    (dev / "src" / "cli" / "admin_cli.py").write_text("")
    _git(dev, "add", "base", "src")
    _git(dev, "commit", "-q", "-m", "base")
    # Stands in for the deployed release's core-admin (CORE_ADMIN below).
    audit = dev / ".venv" / "bin" / "core-admin"
    audit.parent.mkdir(parents=True)
    audit.write_text(FAKE_AUDIT)
    audit.chmod(0o755)
    return dev


@pytest.fixture
def wt(dev: Path, tmp_path: Path) -> Path:
    wt = tmp_path / "wt"
    _git(dev, "worktree", "add", "-q", "-b", "mine", str(wt), "HEAD")
    return wt


def _run(dev: Path, payload: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(dev),
        "CORE_ADMIN": str(dev / ".venv" / "bin" / "core-admin"),
        "FAKE_AUDIT_RECORD": str(dev / "audits.txt"),
    }
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, env=env, capture_output=True, text=True
    )


def _hook(
    dev: Path, command: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {"tool_input": {"command": command}, "cwd": str(cwd or dev), "session_id": "s"}
    )
    return _run(dev, payload)


def _audited(dev: Path) -> list[str]:
    record = dev / "audits.txt"
    return record.read_text().splitlines() if record.exists() else []


# ID: b4521763-2a9b-43e1-a92e-a71038b51d6f
def test_non_commit_commands_pass_without_an_audit(dev: Path) -> None:
    (dev / "BLOCK").write_text("")
    for command in ("git status", "git log --grep commit", "echo 'git commit'"):
        assert _hook(dev, command).returncode == 0
    assert _audited(dev) == []


# ID: 0185551d-0fd5-4b54-b352-109f5b52eba3
def test_a_clean_commit_is_allowed_and_logged_with_its_tree(dev: Path) -> None:
    assert _hook(dev, "git commit -m x").returncode == 0
    assert _audited(dev) == [f"{dev}|{dev}|{dev}/src"]
    log = dev / "var" / "experiments" / "adr168" / "verdicts.jsonl"
    entry = json.loads(log.read_text().splitlines()[-1])
    assert (entry["decision"], entry["tree"], entry["session"]) == (
        "allow",
        str(dev),
        "s",
    )
    assert (entry["check"], entry["verdict"], entry["file_count"]) == (
        "change_verdict",
        "CLEAR_IN_SCOPE",
        2,
    )


# ID: 5ff581c7-51b2-4e86-906d-3d4c30fd617a
def test_a_block_finding_refuses_the_commit(dev: Path) -> None:
    (dev / "BLOCK").write_text("")
    refused = _hook(dev, "git add BLOCK && git commit -m x")
    assert refused.returncode == 2
    assert "fake.rule: BLOCK:1" in refused.stderr
    log = dev / "var" / "experiments" / "adr168" / "verdicts.jsonl"
    entry = json.loads(log.read_text().splitlines()[-1])
    assert (entry["decision"], entry["verdict"], entry["block_rules"]) == (
        "deny",
        "BLOCKED",
        ["fake.rule"],
    )


# ID: 3edd93e0-53dc-4e4e-911c-30be11c06f46
def test_a_change_that_could_not_be_judged_refuses_the_commit(dev: Path) -> None:
    (dev / "UNJUDGED").write_text("")
    refused = _hook(dev, "git commit -m x")
    assert refused.returncode == 2
    assert "NOT_EVALUATED" in refused.stderr
    assert "no rules" in refused.stderr


# ID: 938d8a0e-bc64-4b50-a0cd-5ec6af2ac2b4
def test_a_worktree_commit_audits_the_worktree_not_the_checkout(
    dev: Path, wt: Path
) -> None:
    (dev / "BLOCK").write_text("")
    assert _hook(dev, "git commit -m x", cwd=wt).returncode == 0
    assert _audited(dev) == [f"{wt}|{wt}|{wt}/src"]


# ID: eb315d5b-821b-4716-8e2b-5396d64e6a50
@pytest.mark.parametrize(
    ("command", "in_worktree"),
    [
        ("git commit -m x", True),
        ("git -C {wt} commit -m x", False),
        ("git --no-pager -C {wt} commit -m x", False),
        ("git -c user.name=x commit -m x", True),
        ("/usr/bin/git commit -m x", True),
        ("cd {wt} && git commit -m x", False),
        ("cd {wt}; git commit -m x", False),
    ],
)
def test_every_commit_spelling_in_a_blocked_worktree_is_refused(
    dev: Path, wt: Path, command: str, in_worktree: bool
) -> None:
    (wt / "BLOCK").write_text("")
    refused = _hook(dev, command.format(wt=wt), cwd=wt if in_worktree else dev)
    assert refused.returncode == 2
    assert f"(audited {wt})" in refused.stderr
    assert _audited(dev) == [f"{wt}|{wt}|{wt}/src"]


# ID: bb09ad2f-1479-4547-8c35-b6298d8e391e
def test_another_governed_repository_is_judged_by_its_own_law(
    dev: Path, tmp_path: Path
) -> None:
    """2026-10-15: a commit elsewhere was judged against the development
    checkout. A repository with .intent/ is judged itself, with the
    release's code (no PYTHONPATH); one without .intent/ is not judged."""
    other = tmp_path / "other"
    (other / ".intent").mkdir(parents=True)
    _git(other, "init", "-q")
    assert _hook(dev, "git commit -m x", cwd=other).returncode == 0
    assert _audited(dev) == [f"{other}|{other}|"]

    plain = tmp_path / "plain"
    plain.mkdir()
    _git(plain, "init", "-q")
    assert _hook(dev, "git commit -m x", cwd=plain).returncode == 0
    assert _audited(dev) == [f"{other}|{other}|"]


# ID: deee4a04-040d-4622-98b8-024a4e3d09df
def test_a_missing_release_refuses(dev: Path) -> None:
    payload = json.dumps(
        {
            "tool_input": {"command": "git commit -m x"},
            "cwd": str(dev),
            "session_id": "s",
        }
    )
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(dev),
        "CORE_ADMIN": str(dev / "no-such-core-admin"),
        "FAKE_AUDIT_RECORD": str(dev / "audits.txt"),
    }
    refused = subprocess.run(
        ["bash", str(HOOK)], input=payload, env=env, capture_output=True, text=True
    )
    assert refused.returncode == 2
    assert "no deployed core-admin" in refused.stderr
    assert _audited(dev) == []


# ID: 2873fd07-7209-4605-a961-ff8f19d1d4f0
def test_an_audit_without_a_verdict_fails_closed(dev: Path) -> None:
    (dev / "CRASH").write_text("")
    refused = _hook(dev, "git commit -m x")
    assert refused.returncode == 2
    assert "change check result unreadable" in refused.stderr


# ID: 43d2dd51-cdd7-4544-9982-92d395bb15ef
@pytest.mark.parametrize("payload", ["{not json", "{}", '{"tool_input": {}}'])
def test_an_unreadable_payload_is_refused(dev: Path, payload: str) -> None:
    refused = _run(dev, payload)
    assert refused.returncode == 2
    assert "could not tell whether it commits" in refused.stderr
    assert _audited(dev) == []
