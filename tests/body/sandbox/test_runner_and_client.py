# tests/body/sandbox/test_runner_and_client.py
"""Running a real pytest job through the bootstrap, locally and via the
service handler over a socketpair (ADR-132 D10.10)."""

from __future__ import annotations

import getpass
import os
import socket
import threading
import time
from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler
from body.sandbox import client as client_mod
from body.sandbox.client import SandboxRequest, run_repo_code
from body.sandbox.models import SandboxJob
from body.sandbox.protocol import encode, recv_message
from body.sandbox.runner import child_environment, run_job
from body.sandbox.server import handle_connection, open_snapshot

from .conftest import make_tree


PASSING = "def test_one():\n    assert 1 + 1 == 2\n\ndef test_two():\n    pass\n"
FAILING = "def test_bad():\n    assert False\n"
INTEGRATION = (
    "import pytest\n\n@pytest.mark.integration\ndef test_db():\n    pass\n\n"
    "def test_plain():\n    pass\n"
)


def _job(targets: tuple[str, ...], **kw: object) -> SandboxJob:
    return SandboxJob(
        job_id="b" * 32,
        kind="pytest",
        targets=targets,
        timeout_sec=60,
        **kw,  # type: ignore[arg-type]
    )


def _run(tree: Path, scratch: Path, job: SandboxJob):
    work = scratch / "work"
    work.mkdir(exist_ok=True)
    return run_job(job, snapshot_dir=tree, work_dir=work, isolation="local")


def test_passing_job(scratch: Path) -> None:
    tree = make_tree(scratch / "t", {"test_ok.py": PASSING})
    result = _run(tree, scratch, _job(("tests/test_ok.py",)))
    assert (result.status, result.completeness) == ("passed", "full"), result.stderr
    assert result.counts["executed"] == 2
    assert result.ok


def test_failing_job(scratch: Path) -> None:
    tree = make_tree(scratch / "t", {"test_bad.py": FAILING})
    result = _run(tree, scratch, _job(("tests/test_bad.py",)))
    assert result.status == "failed"
    assert result.counts["failed"] == 1


def test_all_deselected_is_not_run(scratch: Path) -> None:
    tree = make_tree(scratch / "t", {"test_ok.py": PASSING})
    result = _run(tree, scratch, _job(("tests/test_ok.py",), markers="nosuchmarker"))
    assert result.status == "not_run"
    assert not result.ok


def test_integration_exclusion_is_partial(scratch: Path) -> None:
    tree = make_tree(scratch / "t", {"test_mix.py": INTEGRATION})
    result = _run(tree, scratch, _job(("tests/test_mix.py",), exclude_integration=True))
    assert (result.status, result.completeness) == ("passed", "partial")
    assert result.excluded == ["tests/test_mix.py::test_db"]
    assert not result.ok


def test_candidate_code_is_what_runs(scratch: Path) -> None:
    tree = make_tree(
        scratch / "t",
        {
            "test_cand.py": "from sentinel_pkg import VALUE\n\ndef test_v():\n    assert VALUE == 42\n"
        },
        src={"sentinel_pkg/__init__.py": "VALUE = 42\n"},
    )
    result = _run(tree, scratch, _job(("tests/test_cand.py",)))
    assert result.status == "passed", result.stdout + result.stderr


def test_shadowed_package_loaded_from_elsewhere_is_an_error(scratch: Path) -> None:
    # The snapshot ships "json", but the bootstrap imported the stdlib one first.
    tree = make_tree(
        scratch / "t",
        {"test_p.py": "import json\n\ndef test_p():\n    pass\n"},
        src={"json/__init__.py": "\n"},
    )
    result = _run(tree, scratch, _job(("tests/test_p.py",)))
    assert result.status == "error"
    assert "candidate_not_loaded" in result.reason


def test_child_environment_is_an_allow_list(
    scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")
    env = child_environment(scratch)
    assert "DATABASE_URL" not in env
    tree = make_tree(
        scratch / "t",
        {
            "test_env.py": (
                "import os\n\ndef test_env():\n"
                "    assert 'DATABASE_URL' not in os.environ\n"
                "    assert os.path.samestat(os.fstat(0), os.stat(os.devnull))\n"
            )
        },
    )
    (tree / ".env.test").write_text("DATABASE_URL=postgres://from-dotenv\n")
    (tree / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nenv_files = [".env.test"]\n'
        "env_override_existing_values = true\n"
    )
    result = _run(tree, scratch, _job(("tests/test_env.py",)))
    assert result.status == "passed", result.stdout


def test_timeout_kills_the_job_and_its_children(scratch: Path) -> None:
    marker = scratch / "child.pid"
    tree = make_tree(
        scratch / "t",
        {
            "test_slow.py": (
                "import subprocess, time\n\ndef test_slow():\n"
                "    p = subprocess.Popen(['sleep', '600'])\n"
                f"    open({str(marker)!r}, 'w').write(str(p.pid))\n"
                "    time.sleep(600)\n"
            )
        },
    )
    job = SandboxJob(
        job_id="c" * 32, kind="pytest", targets=("tests/test_slow.py",), timeout_sec=5
    )
    started = time.monotonic()
    result = _run(tree, scratch, job)
    assert result.status == "timeout"
    assert time.monotonic() - started < 30
    child = int(marker.read_text())
    time.sleep(0.5)
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_output_is_capped(scratch: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from body.sandbox import runner

    monkeypatch.setattr(runner, "OUTPUT_CAP_BYTES", 2000)
    tree = make_tree(
        scratch / "t",
        {
            "test_loud.py": "def test_loud():\n    print('x' * 100000)\n    assert False\n"
        },
    )
    result = _run(tree, scratch, _job(("tests/test_loud.py",)))
    assert result.output_truncated
    assert len(result.stdout) <= 2000
    assert result.status == "failed"


# --- the service handler, over a socketpair -------------------------------


def _serve(tmp_inbox: Path, scratch: Path, job: SandboxJob, user: str) -> dict:
    server_sock, client_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    env = {
        "CORE_SANDBOX_INBOX_ROOT": str(tmp_inbox),
        "CORE_SANDBOX_WORK_ROOT": str(scratch / "work"),
        "CORE_SANDBOX_CLIENT_USER": user,
    }
    (scratch / "work").mkdir(exist_ok=True)
    thread = threading.Thread(target=handle_connection, args=(server_sock, env))
    thread.start()
    client_sock.sendall(encode({"job": job.to_dict()}))
    try:
        reply = recv_message(client_sock, 8 * 1024 * 1024)
    finally:
        thread.join(timeout=120)
        client_sock.close()
        server_sock.close()
    return reply["result"]


def test_service_handler_runs_a_job_for_the_client_account(scratch: Path) -> None:
    inbox = scratch / "inbox"
    make_tree(inbox / ("d" * 32), {"test_ok.py": PASSING})
    job = SandboxJob(
        job_id="d" * 32, kind="pytest", targets=("tests/test_ok.py",), timeout_sec=60
    )
    result = _serve(inbox, scratch, job, getpass.getuser())
    assert result["status"] == "passed"
    assert result["isolation"] == "service"


def test_service_handler_refuses_another_account(scratch: Path) -> None:
    inbox = scratch / "inbox"
    make_tree(inbox / ("d" * 32), {"test_ok.py": PASSING})
    job = SandboxJob(
        job_id="d" * 32, kind="pytest", targets=("tests/test_ok.py",), timeout_sec=60
    )
    result = _serve(
        inbox, scratch, job, "root" if getpass.getuser() != "root" else "nobody"
    )
    assert result["status"] == "not_run"
    assert "not the client account" in result["reason"]


def test_snapshot_that_is_a_symlink_is_refused(scratch: Path) -> None:
    inbox = scratch / "inbox"
    inbox.mkdir()
    (scratch / "elsewhere").mkdir()
    (inbox / ("e" * 32)).symlink_to(scratch / "elsewhere")
    with pytest.raises(ValueError):
        open_snapshot(inbox, "e" * 32)


# --- the client ------------------------------------------------------------


async def test_client_local_mode_end_to_end(scratch: Path, fh: FileHandler) -> None:
    tree = make_tree(scratch / "t", {"test_ok.py": PASSING})
    result = await run_repo_code(
        SandboxRequest(tree=tree, targets=("tests/test_ok.py",), timeout_sec=60),
        repo_root=fh.repo_path,
        mode="local",
    )
    assert (result.status, result.isolation) == ("passed", "local"), result.stderr
    assert len(result.snapshot_sha256) == 64
    inbox = fh.repo_path / "var" / "tmp" / client_mod.INBOX_DIRNAME
    assert not inbox.exists() or list(inbox.iterdir()) == []


async def test_client_service_mode_without_socket_is_not_run(
    scratch: Path, fh: FileHandler
) -> None:
    tree = make_tree(scratch / "t", {"test_ok.py": PASSING})
    result = await run_repo_code(
        SandboxRequest(tree=tree, targets=("tests/test_ok.py",), timeout_sec=60),
        repo_root=fh.repo_path,
        mode="service",
        socket_path=scratch / "no-such.sock",
    )
    assert result.status == "not_run"
    assert "unavailable" in result.reason
    assert not result.ok


async def test_client_refuses_a_secret_in_the_tree(
    scratch: Path, fh: FileHandler
) -> None:
    tree = make_tree(scratch / "t", {"test_ok.py": PASSING})
    (tree / "tests" / ".env").write_text("DATABASE_URL=postgres://secret\n")
    result = await run_repo_code(
        SandboxRequest(tree=tree, targets=("tests/test_ok.py",), timeout_sec=60),
        repo_root=fh.repo_path,
        mode="local",
    )
    assert result.status == "not_run"
    assert "snapshot refused" in result.reason
