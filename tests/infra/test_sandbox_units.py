"""The sandbox units carry every wall the design names (ADR-132 D10.10).

The walls are the isolation; the server code only refuses and runs. These
tests pin the unit text so a wall cannot be dropped silently. Whether the
walls hold on the host is proven separately, by `core-admin runtime
sandbox-check` (infra/systemd/sandbox/README.md).
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest


UNITS = Path(__file__).resolve().parents[2] / "infra" / "systemd" / "sandbox"


def _directives(name: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    section = ""
    for raw in (UNITS / name).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line.strip("[]")
            continue
        key, _, value = line.partition("=")
        found.setdefault(f"{section}.{key}", []).append(value)
    return found


def test_socket_is_one_job_per_connection_and_group_core_only() -> None:
    d = _directives("core-sandbox.socket")
    assert d["Socket.ListenStream"] == ["/run/core/sandbox.sock"]
    assert d["Socket.Accept"] == ["yes"]
    assert d["Socket.SocketGroup"] == ["core"]
    assert d["Socket.SocketMode"] == ["0660"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("User", "core-sandbox"),
        ("StandardInput", "socket"),
        ("StandardOutput", "journal"),
        ("NoNewPrivileges", "yes"),
        ("CapabilityBoundingSet", ""),
        ("PrivateNetwork", "yes"),
        ("RestrictAddressFamilies", "none"),
        ("PrivateTmp", "yes"),
        ("ProtectHome", "yes"),
        ("ProtectSystem", "strict"),
        ("ReadOnlyPaths", "/opt/core/repo/var/tmp/sandbox-inbox"),
        ("SystemCallArchitectures", "native"),
        ("SystemCallFilter", "~io_uring_setup io_uring_enter io_uring_register"),
        ("KillMode", "control-group"),
        ("Environment", "CORE_SANDBOX_CLIENT_USER=core"),
    ],
)
def test_service_carries_each_wall(key: str, value: str) -> None:
    assert value in _directives("core-sandbox@.service").get(f"Service.{key}", [])


def test_secrets_and_dev_tree_are_inaccessible() -> None:
    (paths,) = _directives("core-sandbox@.service")["Service.InaccessiblePaths"]
    for required in ("-/opt/core/etc", "-/opt/dev", "-/opt/core-law", "-/run/dbus", "-/run/docker.sock", "-/run/core"):
        assert required in paths.split()


def test_service_runs_the_release_isolated_not_the_dev_tree() -> None:
    (cmd,) = _directives("core-sandbox@.service")["Service.ExecStart"]
    assert cmd.startswith("/opt/core/current/venv/bin/python -I -m body.sandbox.server")
    assert "/opt/dev" not in cmd


def test_runtime_ceiling_covers_the_longest_job() -> None:
    from body.sandbox.models import MAX_TIMEOUT_SEC

    (ceiling,) = _directives("core-sandbox@.service")["Service.RuntimeMaxSec"]
    assert int(ceiling) > MAX_TIMEOUT_SEC


def test_configparser_reads_both_units() -> None:
    for name in ("core-sandbox.socket", "core-sandbox@.service"):
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        parser.optionxform = str  # type: ignore[assignment,method-assign]
        parser.read(UNITS / name)
        assert parser.sections()


def test_run_is_not_replaced_by_a_tmpfs() -> None:
    # systemd 255 needs /run/systemd/incoming while it builds the namespace;
    # a tmpfs over /run made every job exit 226/NAMESPACE (2026-10-12).
    tmpfs = _directives("core-sandbox@.service").get("Service.TemporaryFileSystem", [])
    for entry in tmpfs:
        for path in entry.split():
            assert path.split(":")[0] not in ("/run", "/var/run")
