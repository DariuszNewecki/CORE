# src/body/sandbox/probes.py
"""
Closure probes for the sandbox (ADR-132 D10.10, milestone M1).

Each probe is a pytest test that *passes only if a wall holds*. It is
written into a probe tree and run through ``run_repo_code`` like any job,
one job per probe, so each wall gets its own result:

- ``ordinary``: an ordinary test passes (the sandbox is usable);
- ``secrets``: the service's secret files cannot be read;
- ``secret_link``: a symlink in the snapshot pointing at a secret cannot be
  read through;
- ``tcp``: no TCP connection, to the database port or outside;
- ``host_sockets``: the host's Unix sockets (docker, dbus) cannot be reached;
- ``new_socket``: no new network socket can be created;
- ``inbox_read_only``: the snapshot cannot be written;
- ``leftover``: a detached child is started and left behind (the test
  fails on purpose to report its pid); afterwards it must be gone, checked
  by the caller from outside the job.

In ``local`` mode most walls are expected to fail: that mode does not
isolate, and the report says so. The fail-closed probe (socket stopped →
``not_run``) is the governor's step: stop ``core-sandbox.socket`` and run
the battery again; every probe must then be ``not_run``.

CONSTITUTIONAL ALIGNMENT:
- Writes the probe tree only through FileHandler, under var/tmp.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from body.infrastructure.storage.file_handler import FileHandler
from body.sandbox.client import DEFAULT_SOCKET, SandboxRequest, run_repo_code
from shared.path_resolver import PathResolver


SECRET_PATHS: tuple[str, ...] = (
    "/opt/core/etc/secrets.env",
    "/opt/core/etc/core.env",
    "/opt/dev/CORE/.env",
)
HOST_SOCKETS: tuple[str, ...] = ("/run/docker.sock", "/run/dbus/system_bus_socket")
TCP_TARGETS: tuple[tuple[str, int], ...] = (("127.0.0.1", 5432), ("1.1.1.1", 443))
PROBE_DIRNAME = "sandbox-probe"

_PROBES = """
import os
import socket
import subprocess

import pytest

SECRET_PATHS = {secrets!r}
HOST_SOCKETS = {sockets!r}
TCP_TARGETS = {tcp!r}
LEFTOVER_PID_FILE = os.path.join(os.environ.get("TMPDIR", "."), "leftover.pid")


def _denied(fn):
    try:
        fn()
    except OSError:
        return True
    return False


def test_ordinary():
    assert sum(range(5)) == 10


def test_secrets():
    for path in SECRET_PATHS:
        assert _denied(lambda: open(path, "rb").read(1)), path


def test_secret_link():
    # The link sits in src/, not tests/: pytest stats every entry of a
    # directory it collects, and an unreadable target stops collection.
    link = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "secret_link")
    assert os.path.islink(link)
    assert _denied(lambda: open(link, "rb").read(1))


def test_tcp():
    for host, port in TCP_TARGETS:
        assert _denied(lambda: socket.create_connection((host, port), timeout=3)), host


def test_host_sockets():
    for path in HOST_SOCKETS:
        def connect():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(path)
        assert _denied(connect), path


def test_new_socket():
    assert _denied(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))


def test_inbox_read_only():
    target = os.path.join(os.path.dirname(__file__), "written.txt")
    assert _denied(lambda: open(target, "w").write("x"))
    assert _denied(lambda: os.chmod(__file__, 0o666))


def test_leftover():
    child = subprocess.Popen(["sleep", "600"], start_new_session=True)
    pytest.fail("LEFTOVER_PID=%d" % child.pid)  # read by the caller
"""

PROBE_NAMES: tuple[str, ...] = (
    "ordinary",
    "secrets",
    "secret_link",
    "tcp",
    "host_sockets",
    "new_socket",
    "inbox_read_only",
    "leftover",
)


# ID: 8594bbcd-6082-47f0-8849-7d584b2922fd
def probe_source() -> str:
    """The probe test module, with this host's targets filled in."""
    return _PROBES.format(secrets=SECRET_PATHS, sockets=HOST_SOCKETS, tcp=TCP_TARGETS)


# ID: 837738ca-89e5-4382-8514-294cf8c68791
async def run_probes(
    repo_root: Path, *, mode: str, socket_path: Path = DEFAULT_SOCKET
) -> list[dict[str, Any]]:
    """Run every probe as its own job; one row per probe."""
    handler = FileHandler(str(repo_root))
    tmp_rel = PathResolver(repo_root).tmp_dir.relative_to(handler.repo_path)
    tree_rel = tmp_rel / PROBE_DIRNAME / uuid.uuid4().hex
    handler.write_runtime_text(
        str(tree_rel / "tests" / "test_walls.py"), probe_source()
    )
    handler.write_runtime_text(
        str(tree_rel / "pyproject.toml"), "[tool.pytest.ini_options]\n"
    )
    handler.ensure_dir(str(tree_rel / "src"))
    handler.create_symlink(str(tree_rel / "src" / "secret_link"), SECRET_PATHS[0])
    tree = handler.repo_path / tree_rel
    rows: list[dict[str, Any]] = []
    try:
        for name in PROBE_NAMES:
            result = await run_repo_code(
                SandboxRequest(
                    tree=tree,
                    targets=(f"tests/test_walls.py::test_{name}",),
                    timeout_sec=60,
                ),
                repo_root=repo_root,
                mode=mode,
                socket_path=socket_path,
            )
            row: dict[str, Any] = {
                "probe": name,
                "status": result.status,
                "isolation": result.isolation,
                "reason": result.reason,
            }
            if name == "leftover":
                alive = _leftover_alive(result.stdout)
                row["leftover_alive"] = alive
                if alive is False:
                    row.update(status="passed", reason="")
                elif alive:
                    row.update(
                        status="failed", reason="a detached child outlived its job"
                    )
            rows.append(row)
    finally:
        handler.remove_tree(str(tree_rel))
    return rows


def _leftover_alive(stdout: str) -> bool | None:
    match = re.search(r"LEFTOVER_PID=(\d+)", stdout)
    if match:
        pid = int(match.group(1))
        time.sleep(1.0)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # exists, owned by another account
        return True
    return None
