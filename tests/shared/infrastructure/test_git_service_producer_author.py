# tests/shared/infrastructure/test_git_service_producer_author.py
"""A6: a proposal's producer is the git author, CORE the committer (real git).
ADR-168 Amendment 2026-10-10; producer build U5."""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.infrastructure.git_service import (
    GitService,
    autonomous_identity,
    producer_identity,
)


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(root: Path) -> GitService:
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "person@example.invalid"], root)
    _run(["git", "config", "user.name", "A Person"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)
    (root / "seed.txt").write_text("seed\n")
    _run(["git", "add", "seed.txt"], root)
    _run(["git", "commit", "-q", "-m", "initial"], root)
    return GitService(root)


# ID: 37020be6-3862-4b65-98b8-a5371e6248ce
def test_producer_identity_is_the_producer_on_cores_invalid_domain() -> None:
    domain = autonomous_identity()[1].rpartition("@")[2]
    assert producer_identity("claude-session:core-darek") == (
        "claude-session:core-darek",
        f"claude-session-core-darek@{domain}",
    )
    assert producer_identity("core:fix.format")[1] == f"core-fix.format@{domain}"
    assert producer_identity("  ")[1] == f"producer@{domain}"


# ID: 968de140-2804-492d-aee9-0e71a040ab7d
def test_commit_names_producer_as_author_and_core_as_committer(tmp_path: Path) -> None:
    svc = _repo(tmp_path)
    (tmp_path / "produced.py").write_text("x = 1\n")

    svc.commit_paths(
        ["produced.py"],
        "fix(p): produced",
        identity=autonomous_identity(),
        author=producer_identity("claude-session:core-darek"),
    )

    who = _run(["git", "log", "-1", "--format=%an|%ae|%cn|%ce"], tmp_path).split("|")
    core_name, core_email = autonomous_identity()
    assert who[0] == "claude-session:core-darek"
    assert who[1].startswith("claude-session-core-darek@")
    assert who[2:] == [core_name, core_email]


# ID: d85d8676-f80e-4751-8750-c19bec1f4427
def test_without_author_both_are_the_identity(tmp_path: Path) -> None:
    svc = _repo(tmp_path)
    (tmp_path / "produced.py").write_text("x = 1\n")

    svc.commit_paths(
        ["produced.py"], "fix(p): produced", identity=autonomous_identity()
    )

    who = _run(["git", "log", "-1", "--format=%an|%cn"], tmp_path).split("|")
    assert who == [autonomous_identity()[0]] * 2
