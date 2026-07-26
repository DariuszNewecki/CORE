# tests/cli/logic/demo/test_consequence_chain_real_sigint.py
"""E12 (full): a genuine OS-level SIGINT to a real, in-flight
`core-admin demo consequence-chain` process (ADR-155 §5 exit code 130, D11).

``test_isolation.py``'s E12 case (partial, in-process) and
``test_consequence_chain_cmd.py``'s ``test_interrupt_exits_130`` /
``test_cancelled_exits_130`` all prove the *handler* is wired correctly by
injecting a ``KeyboardInterrupt``/``CancelledError`` inline, in-process, into
the same test function's call stack — none of them send a real signal to a
real OS process. ``test_e12_partial_cancellation_during_compose_up_leaves_
cleanup_intact`` says so explicitly: "Full E12 coverage (SIGINT -> process
exit code 130) requires a CLI entrypoint that installs a signal handler and
translates it to an exit code — that's Phase 3." Phase 3 (``cli.resources.
demo.consequence_chain``) now exists; this is that full coverage.

This test launches the real `core-admin demo consequence-chain` command as
its own OS process (in a fresh process group via ``start_new_session=True``,
the same relationship a terminal's foreground process group has to Ctrl+C),
waits for the real child `scenario_runner.py` OS process it spawns to
actually appear (proof of a genuinely in-flight run — Compose containers are
already up and healthy by the time that child exists), sends a real
``SIGINT`` to the process group, and verifies: exit code 130, no surviving
Docker containers/networks labelled with the run's id, and no orphaned
`scenario_runner.py` process.

Needs real Docker and takes real wall-clock time (a live Postgres+Qdrant
Compose project, a real audit-sensor pass over a full repo clone). Skipped
when Docker is unavailable, same convention as ``test_compose_lifecycle.py``
/ ``test_consequence_chain_e2e.py``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[4]

_CHILD_SPAWN_TIMEOUT_SECONDS = 90.0
_POLL_INTERVAL_SECONDS = 0.1
_EXIT_WAIT_TIMEOUT_SECONDS = 120.0


def _find_scenario_runner_child(parent_pid: int) -> tuple[int, str] | None:
    """Return ``(pid, run_id)`` for the real ``scenario_runner.py`` process
    that is a direct child of *parent_pid*, or ``None`` if it isn't running
    yet. ``-P`` scopes the match to a direct child of the launched CLI
    process, so this can never accidentally match an unrelated process on
    the box that happens to mention the same script name."""
    try:
        result = subprocess.run(
            ["pgrep", "-af", "-P", str(parent_pid), "scenario_runner.py"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = next((line for line in result.stdout.splitlines() if line.strip()), None)
    if line is None:
        return None
    parts = line.split()
    pid = int(parts[0])
    # Invocation shape (scenario_runner.py's own _main): [python, script,
    # state_dir, seed_rel_path, run_id] — run_id is always the last token.
    run_id = parts[-1]
    return pid, run_id


def _docker_labelled_resources(filter_kind: str, run_id: str) -> list[str]:
    args = (
        ["docker", "ps", "-a"]
        if filter_kind == "container"
        else ["docker", "network", "ls"]
    )
    args += ["--filter", f"label=core.demo.run_id={run_id}", "--format", "{{.Names}}"]
    out = subprocess.run(args, capture_output=True, text=True, timeout=15).stdout
    return [line for line in out.splitlines() if line.strip()]


# ID: 6e9a4a53-6b3f-4b0e-9f0c-2b6c9c9a2f77
def test_e12_real_sigint_to_live_child_exits_130_and_leaves_no_survivors(
    docker_compose_available: bool, tmp_path: Path
) -> None:
    if not docker_compose_available:
        pytest.skip("docker compose v2 not available")

    # The launched process must boot with none of this test's own ambient
    # env config (e.g. pytest-dotenv loaded `.env.test`'s shared-LAN
    # DATABASE_URL/QDRANT_URL into this process's os.environ per
    # `env_override_existing_values = true`). The demo's own disposable
    # Postgres/Qdrant come from Docker Compose, never from ambient config —
    # stripping these also proves that structurally, not just by inspection.
    env = dict(os.environ)
    for key in ("DATABASE_URL", "QDRANT_URL", "CORE_ENV"):
        env.pop(key, None)
    # `poetry run core-admin` resolves `import shared` etc. against the
    # editable install (this checkout's `/opt/dev/CORE-demo-consequence-chain`
    # own `pyproject.toml` `packages` — NOT necessarily this checkout's
    # working tree unless PYTHONPATH is forced) — see CLAUDE.md's
    # environment-gotchas note; PYTHONPATH=src makes this checkout's own
    # src/ win.
    env["PYTHONPATH"] = "src"
    # Keep the run's disposable state under this test's own tmp_path so a
    # crashed/killed run never leaves anything under the real
    # ~/.local/state/core/demo directory.
    env["CORE_DEMO_STATE_DIR"] = str(tmp_path / "demo_state")

    log_path = tmp_path / "consequence_chain_sigint.log"
    with open(log_path, "wb") as log_file:
        proc = subprocess.Popen(
            [
                "poetry",
                "run",
                "core-admin",
                "demo",
                "consequence-chain",
                "--simulate-confirmation",
                "--timeout-seconds",
                "240",
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        try:
            child = None
            deadline = time.monotonic() + _CHILD_SPAWN_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                child = _find_scenario_runner_child(proc.pid)
                if child is not None:
                    break
                if proc.poll() is not None:
                    pytest.fail(
                        f"CLI process exited (code {proc.returncode}) before "
                        f"spawning scenario_runner.py — see {log_path}:\n"
                        f"{log_path.read_text(errors='replace')}"
                    )
                time.sleep(_POLL_INTERVAL_SECONDS)

            assert child is not None, (
                f"scenario_runner.py child never appeared within "
                f"{_CHILD_SPAWN_TIMEOUT_SECONDS}s — see {log_path}"
            )
            _child_pid, run_id = child

            # A brief buffer past first observation: the child is doing real
            # work (a full AuditViolationSensor pass over the cloned repo)
            # for several more seconds — this is comfortably mid-flight, not
            # racing the child's own startup.
            time.sleep(0.5)

            # The real, OS-level signal under test — sent to the whole
            # process group, exactly as a terminal's Ctrl+C would reach both
            # the CLI process and the child it spawned.
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGINT)

            try:
                exit_code = proc.wait(timeout=_EXIT_WAIT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
                proc.wait(timeout=10)
                pytest.fail(
                    f"process did not exit within {_EXIT_WAIT_TIMEOUT_SECONDS}s "
                    f"after SIGINT — see {log_path}"
                )

            log_text = log_path.read_text(errors="replace")
            assert exit_code == 130, (
                f"expected exit 130 (ADR-155 §5 operator interruption), got "
                f"{exit_code}. Output tail:\n{log_text[-4000:]}"
            )

            # No surviving Docker containers or networks for this run.
            containers = _docker_labelled_resources("container", run_id)
            assert not containers, f"containers survived SIGINT+cleanup: {containers}"
            networks = _docker_labelled_resources("network", run_id)
            assert not networks, f"networks survived SIGINT+cleanup: {networks}"

            # No orphaned scenario_runner.py process for this run remains.
            # (A brief grace period for the OS to finish reaping.)
            deadline = time.monotonic() + 5.0
            orphan_lines: list[str] = []
            while time.monotonic() < deadline:
                result = subprocess.run(
                    ["pgrep", "-af", "scenario_runner.py"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                orphan_lines = [
                    line
                    for line in result.stdout.splitlines()
                    if run_id in line
                ]
                if not orphan_lines:
                    break
                time.sleep(0.2)
            assert not orphan_lines, (
                f"orphan scenario_runner.py process for run {run_id} still "
                f"alive after SIGINT: {orphan_lines}"
            )
        finally:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=10)
