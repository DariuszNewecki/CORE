"""The `.claude/hooks` private-names gate (process-governance-tool privacy rule).

A real git repository stands in for the governed checkout; its origin/main
carries a stand-in enforcer (scripts/private_names.py) that refuses text
holding any Markdown file stem of the stand-in private library. The hook must
pass everything when the host holds no private library, run the merged
enforcer before a commit in that checkout and before a gh write aimed at its
repository, block on a hit without repeating the name, and refuse what it
cannot check (a body from stdin, an unreadable body file, no enforcer).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
# The source of the copy installed in .claude/hooks/ (core-law, not in git).
HOOK = REPO / "infra" / "claude-hooks" / "core-private-names.py"

FAKE_ENFORCER = """import os, pathlib, sys
lib = os.environ.get("PROCGOV_PRIVATE_LIBRARY")
if not lib:
    print("private_names: nothing to check"); sys.exit(0)
names = [p.stem.lower() for p in pathlib.Path(lib).glob("*.md")]
text = " ".join(pathlib.Path(a).read_text().lower() for a in sys.argv[1:])
hit = [n for n in names if n in text]
print("private_names: a private library name" if hit else "private_names: clean")
sys.exit(1 if hit else 0)
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
def host(tmp_path: Path) -> dict[str, Path]:
    dev = tmp_path / "dev"
    dev.mkdir()
    _git(dev, "init", "-q")
    (dev / "base").write_text("base")
    _git(dev, "add", "base")
    _git(dev, "commit", "-q", "-m", "base")
    checkout = tmp_path / "pgt"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / ".intent").mkdir()
    (checkout / ".intent" / "x.yaml").write_text("x: 1\n")
    (checkout / "scripts" / "private_names.py").write_text(FAKE_ENFORCER)
    _git(checkout, "init", "-q")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-q", "-m", "base")
    _git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    library = tmp_path / "private"
    library.mkdir()
    (library / "Quarry_Plan.md").write_text("# Plan\n")
    conf = tmp_path / "private-names.conf"
    conf.write_text(
        f"GITHUB_REPO=owner/pgt-tool\nCHECKOUT={checkout}\nLIBRARY={library}\n"
    )
    return {"dev": dev, "checkout": checkout, "conf": conf, "tmp": tmp_path}


def _hook(
    host: dict[str, Path], command: str, cwd: Path | None = None, conf: bool = True
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(host["dev"]),
        "CORE_PRIVATE_NAMES_CONF": str(host["conf"] if conf else host["tmp"] / "none"),
        "CORE_PRIVATE_NAMES_PYTHON": sys.executable,
    }
    payload = json.dumps(
        {"tool_input": {"command": command}, "cwd": str(cwd or host["dev"])}
    )
    return subprocess.run(
        [sys.executable, "-I", str(HOOK)],
        input=payload,
        env=env,
        capture_output=True,
        text=True,
    )


# ID: 890275f4-3414-4891-9a6e-c833481f8098
def test_a_host_without_a_private_library_passes_everything(host) -> None:
    command = "gh issue create -R owner/pgt-tool --body 'Quarry_Plan'"
    assert _hook(host, command, conf=False).returncode == 0


# ID: c8038ebf-a57e-41b8-92b6-dc49b0a65ae2
def test_a_gh_write_naming_a_private_file_is_blocked_without_the_name(host) -> None:
    refused = _hook(
        host, "gh issue create -R owner/pgt-tool --title t --body 'see Quarry_Plan'"
    )
    assert refused.returncode == 2
    assert "private library" in refused.stderr and "Quarry" not in refused.stderr


# ID: 7fb8fe7b-4547-4a59-84e7-3990724f5545
def test_a_plain_description_passes(host) -> None:
    assert (
        _hook(
            host, "gh issue create -R owner/pgt-tool --body 'the plan, v0.3'"
        ).returncode
        == 0
    )


# ID: bbf2bc8c-e4c0-452e-8824-71d8cc8223c6
def test_body_files_are_read_and_checked(host) -> None:
    body = host["tmp"] / "body.md"
    body.write_text("found in Quarry_Plan\n")
    for command in (
        f"gh pr create --repo owner/pgt-tool --body-file {body}",
        f"gh api repos/owner/pgt-tool/issues/1/comments -F body=@{body}",
        f"gh api -X PATCH repos/owner/pgt-tool/pulls/2 --input={body}",
    ):
        assert _hook(host, command).returncode == 2, command
    body.write_text("clean\n")
    assert (
        _hook(host, f"gh pr comment 3 -R owner/pgt-tool --body-file {body}").returncode
        == 0
    )


# ID: dd73b740-3177-4708-91b2-6bfc0097e9eb
def test_what_cannot_be_checked_is_refused(host) -> None:
    missing = host["tmp"] / "missing.md"
    assert (
        _hook(
            host, f"gh issue comment 1 -R owner/pgt-tool --body-file {missing}"
        ).returncode
        == 2
    )
    stdin = _hook(host, "gh issue comment 1 -R owner/pgt-tool --body-file -")
    assert stdin.returncode == 2 and "stdin" in stdin.stderr


# ID: 6e65d6fa-8b4f-4424-af89-2c19488aec8e
def test_gh_inside_the_checkout_is_aimed_at_its_repository(host) -> None:
    command = "gh issue comment 1 --body 'Quarry_Plan'"
    assert _hook(host, command, cwd=host["checkout"]).returncode == 2
    assert _hook(host, command, cwd=host["dev"]).returncode == 0
    other = "gh issue comment 1 -R owner/other --body 'Quarry_Plan'"
    assert _hook(host, other, cwd=host["checkout"]).returncode == 0


# ID: 1da6bebc-b67d-401b-a256-0a007b461747
def test_reads_and_other_commands_pass(host) -> None:
    for command in (
        "gh issue view 1 -R owner/pgt-tool",
        "echo Quarry_Plan",
        "git status",
    ):
        assert _hook(host, command, cwd=host["checkout"]).returncode == 0, command


# ID: 8d4690e1-08c3-4820-9453-980b605e21e6
def test_a_commit_in_the_checkout_is_checked_in_message_diff_and_new_files(
    host,
) -> None:
    checkout = host["checkout"]
    assert (
        _hook(host, "git commit -m 'fix for Quarry_Plan'", cwd=checkout).returncode == 2
    )
    (checkout / "notes.txt").write_text("from quarry_plan\n")
    assert (
        _hook(host, "git add notes.txt && git commit -m x", cwd=checkout).returncode
        == 2
    )
    (checkout / "notes.txt").write_text("clean\n")
    assert (
        _hook(host, "git add notes.txt && git commit -m x", cwd=checkout).returncode
        == 0
    )
    (checkout / "Quarry_Plan.txt").write_text("clean\n")
    assert _hook(host, f"git -C {checkout} commit -am x").returncode == 2
    assert _hook(host, "git commit -m 'Quarry_Plan'", cwd=host["dev"]).returncode == 0


# ID: c68285f6-9432-4a15-8281-a4e1e01d1065
def test_without_the_merged_enforcer_the_action_is_refused(host) -> None:
    _git(host["checkout"], "update-ref", "-d", "refs/remotes/origin/main")
    refused = _hook(host, "gh issue create -R owner/pgt-tool --body 'clean'")
    assert refused.returncode == 2 and "no enforcer" in refused.stderr
