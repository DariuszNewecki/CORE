"""first_seen_date / introducing_commit_subject follow renames (real git).

`.intent/workers/audit_sensor_cli.yaml` was added 2026-03-13 and renamed
2026-05-29; without `--follow` ROW4 dated it to the rename and flagged it as
post-topology (CCC run 6558a043).
"""

from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

from shared.infrastructure.git_service import GitService


def _git(cwd: Path, *args: str, when: str | None = None) -> None:
    env = dict(os.environ)
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


# ID: 90effbc2-2df0-4498-9f69-43fc1d9c0dc6
def test_first_seen_and_introducing_subject_follow_a_rename(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.invalid")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "old.yaml").write_text("name: worker\nbody: unchanged content\n")
    _git(tmp_path, "add", "old.yaml")
    _git(
        tmp_path,
        "commit",
        "-q",
        "-m",
        "feat: ADR-012 add worker",
        when="2026-03-13T10:00:00",
    )
    _git(tmp_path, "mv", "old.yaml", "new.yaml")
    _git(tmp_path, "commit", "-q", "-m", "chore: rename", when="2026-05-29T10:00:00")

    git = GitService(tmp_path)

    assert git.first_seen_date("new.yaml") == date(2026, 3, 13)
    assert git.introducing_commit_subject("new.yaml") == "feat: ADR-012 add worker"
