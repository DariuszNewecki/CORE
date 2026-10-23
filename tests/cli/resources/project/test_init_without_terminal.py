"""`project init --write` without a terminal (review P1).

An open stdin that is not a terminal (CI, scripts, AI agents) used to sit at
"CONFIRM DANGEROUS OPERATION" forever. Now it stops at once and names
--yes; --yes skips the prompt; at a real terminal the prompt is unchanged.
"""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path


SRC = Path(
    os.environ.get("CORE_TEST_SRC") or Path(__file__).resolve().parents[4] / "src"
)


def _env() -> dict[str, str]:
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
    env["PYTHONPATH"] = str(SRC)
    return env


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def _run_with_open_pipe(repo: Path, *args: str, timeout: float = 60):
    """Run core-admin with a stdin pipe that stays open and never answers."""
    log = repo.parent / "out.txt"
    with log.open("w") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "cli.admin_cli", *args],
            cwd=repo,
            env=_env(),
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
        start = time.monotonic()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise AssertionError(f"core-admin {' '.join(args)} hung for {timeout}s")
        finally:
            assert proc.stdin is not None
            proc.stdin.close()
        elapsed = time.monotonic() - start
    return proc.returncode, log.read_text(errors="replace"), elapsed


def _startup_seconds(repo: Path) -> float:
    start = time.monotonic()
    subprocess.run(
        [sys.executable, "-m", "cli.admin_cli", "project", "init", "--help"],
        cwd=repo,
        env=_env(),
        capture_output=True,
        timeout=120,
        check=True,
    )
    return time.monotonic() - start


def test_no_terminal_without_yes_stops_at_once_and_writes_nothing(tmp_path) -> None:
    repo = _repo(tmp_path)
    before = _startup_seconds(repo)
    code, out, elapsed = _run_with_open_pipe(repo, "project", "init", ".", "--write")
    # Start-up under load varies; take the slower of a run either side.
    startup = max(before, _startup_seconds(repo))
    assert code != 0
    assert "rerun with --yes" in out
    assert "core-admin project init . --write needs confirmation" in out
    # The CLI's own start-up is the floor; past it, no more than 2 s.
    assert elapsed < startup + 2, (elapsed, startup)
    assert not (repo / ".intent").exists()


def test_no_terminal_with_yes_completes_and_writes(tmp_path) -> None:
    repo = _repo(tmp_path)
    code, out, _ = _run_with_open_pipe(repo, "project", "init", ".", "--write", "--yes")
    assert code == 0, out
    assert "CONFIRM DANGEROUS OPERATION" not in out
    assert (repo / ".intent").is_dir()


def _run_at_terminal(repo: Path, answer: bytes | None, *args: str):
    """Run core-admin on a real pseudo-terminal, answering the prompt."""
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.chdir(repo)
        os.execve(
            sys.executable, [sys.executable, "-m", "cli.admin_cli", *args], _env()
        )
    out, answered, deadline = b"", False, time.monotonic() + 120
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 1)
        if not ready:
            continue
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if answer is not None and not answered and b"[y/n]" in out:
            os.write(fd, answer)
            answered = True
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace")


def test_at_a_terminal_the_prompt_is_unchanged_and_yes_skips_it(tmp_path) -> None:
    declined = _repo(tmp_path / "n")
    code, out = _run_at_terminal(declined, b"n\n", "project", "init", ".", "--write")
    assert "CONFIRM DANGEROUS OPERATION" in out
    assert code == 0 and "Cancelled." in out
    assert not (declined / ".intent").exists()

    accepted = _repo(tmp_path / "y")
    code, out = _run_at_terminal(accepted, b"y\n", "project", "init", ".", "--write")
    assert "CONFIRM DANGEROUS OPERATION" in out
    assert code == 0 and (accepted / ".intent").is_dir()

    skipped = _repo(tmp_path / "yes")
    code, out = _run_at_terminal(
        skipped, None, "project", "init", ".", "--write", "--yes"
    )
    assert "CONFIRM DANGEROUS OPERATION" not in out
    assert code == 0 and (skipped / ".intent").is_dir()
