"""core-runtime-setup (ADR-132 D10 · D2, D10.10): the governor's root act that
prepares the release runtime and the sandbox runner.

The real script runs against a temporary layout with a scripted Host:
accounts, ownership, processes and HTTP are simulated and recorded, so these
tests prove the procedure -- what runs as which account, where every
installed byte comes from, what a plan-only run leaves alone, what a re-run
keeps -- without root. Modes are real (chmod on the temporary tree). The
real accounts, units and denials are proven when the governor runs it: its
own probes (step 8), then core-deploy and the sandbox check.
"""

from __future__ import annotations

import datetime
import importlib.machinery
import importlib.util
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "infra" / "core-runtime-setup"
SHA = "a" * 40


def _load(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve the module by name
    loader.exec_module(module)
    return module


rs = _load("core_runtime_setup", SCRIPT)

CORE_ENV = (
    b"REPO_PATH=/opt/core/repo\n"
    b"CORE_UPSTREAM_URL=https://github.com/DariuszNewecki/CORE.git\n"
    b"CORE_SANDBOX_MODE=service\n"
)


def _content(rel: str) -> bytes:
    if rel.endswith("core.env.example"):
        return CORE_ENV
    return f"# fetched {rel}\n".encode()


class FakeHost(rs.Host):
    def __init__(self, home: Path) -> None:
        self.root = True
        self.accounts = {
            "core": SimpleNamespace(pw_shell="/bin/bash", pw_dir=str(home / "core")),
        }
        self.groups: dict[str, list[str]] = {}
        self.owners: dict[Path, tuple[str, str]] = {}
        self.calls: list[tuple[list[str], str | None]] = []
        self.fetched: list[str] = []
        self.socket_active = False
        self.readable_etc_by: set[str] = set()

    def is_root(self) -> bool:
        return self.root

    def account(self, name: str):  # type: ignore[override]
        return self.accounts.get(name)

    def groups_of(self, user: str) -> list[str]:
        return self.groups.get(user, [user])

    def fetch(self, url: str, timeout: float = 30.0) -> bytes:
        self.fetched.append(url)
        return _content(url.split(f"/{SHA}/", 1)[1])

    def owner(self, path: Path) -> tuple[str, str]:
        return self.owners.get(path, ("root", "root"))

    def chown(self, path: Path, user: str, group: str) -> None:
        self.owners[path] = (user, group)

    def now(self) -> datetime.datetime:
        return datetime.datetime(2026, 10, 12, 8, 0, tzinfo=datetime.UTC)

    def run(self, cmd, *, user=None, cwd=None, check=True):  # type: ignore[override]
        self.calls.append((list(cmd), user))
        out, code = b"", 0
        if cmd[0] == "useradd":
            self.accounts[cmd[-1]] = SimpleNamespace(
                pw_shell="/usr/sbin/nologin", pw_dir="/nonexistent"
            )
        elif cmd[0] == "git" and "clone" in cmd:
            repo = Path(cmd[-1])
            (repo / ".git").mkdir(parents=True)
            (repo / "var" / "prompts").mkdir(parents=True)
        elif cmd[0] == "git" and cmd[-2:] == ["sparse-checkout", "list"]:
            out = "\n".join(rs.SPARSE).encode()
        elif cmd[0] == "git" and cmd[-2:] == ["rev-parse", "HEAD"]:
            out = SHA.encode()
        elif cmd[:2] == ["systemctl", "is-active"]:
            code = 0 if self.socket_active else 3
        elif cmd[:3] == ["systemctl", "enable", "--now"]:
            self.socket_active = True
        elif cmd[0] == "cat" and user is not None:
            code = 0 if user in self.readable_etc_by else 1
        result = subprocess.CompletedProcess(cmd, code, out, b"")
        if check and code:
            raise rs.Refused(f"failed: {cmd}")
        return result


@pytest.fixture
def world(tmp_path: Path):
    layout = rs.Layout(
        core_root=tmp_path / "opt" / "core",
        dev_repo=tmp_path / "dev" / "CORE",
        system_units=tmp_path / "etc" / "systemd" / "system",
        sbin=tmp_path / "usr" / "local" / "sbin",
    )
    (layout.law / ".intent").mkdir(parents=True)
    layout.dev_secrets.parent.mkdir(parents=True)
    layout.dev_secrets.write_bytes(b"DATABASE_URL=postgres://x\nCORE_MASTER_KEY=k\n")
    layout.system_units.mkdir(parents=True)
    layout.sbin.mkdir(parents=True)
    # Today's units: an old daemon unit and the drop-in that loads the dev tree.
    units = tmp_path / "home" / "core" / ".config" / "systemd" / "user"
    (units / "core-daemon.service.d").mkdir(parents=True)
    (units / "core-daemon.service").write_text("ExecStart=/opt/dev/CORE/.venv/bin/x\n")
    (units / "core-daemon.service.d" / "env.conf").write_text(
        f"[Service]\nEnvironmentFile={layout.dev_repo}/.env\n"
    )
    host = FakeHost(tmp_path / "home")
    return SimpleNamespace(layout=layout, host=host, units=units, tmp=tmp_path)


def _run(world, *extra: str) -> int:
    return rs.main(["--ref", SHA, *extra], host=world.host, layout=world.layout)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _ran(world, first: str) -> list[tuple[list[str], str | None]]:
    return [c for c in world.host.calls if c[0][0] == first]


# -- refusals ---------------------------------------------------------------


def test_refuses_without_root(world) -> None:
    world.host.root = False
    assert _run(world, "--apply") == 1
    assert world.host.calls == []


def test_refuses_a_ref_that_is_not_a_full_sha(world) -> None:
    assert rs.main(["--ref", "develop"], host=world.host, layout=world.layout) == 1
    assert world.host.fetched == []


def test_refuses_before_core_law_setup(world) -> None:
    (world.layout.law / ".intent").rmdir()
    assert _run(world, "--apply") == 1
    assert world.host.calls == []


def test_refuses_an_existing_account_with_a_login_shell(world) -> None:
    world.host.accounts["core-build"] = SimpleNamespace(
        pw_shell="/bin/bash", pw_dir="/home/core-build"
    )
    assert _run(world, "--apply") == 1
    assert not _ran(world, "useradd")


# -- plan only ----------------------------------------------------------------


def test_plan_only_changes_nothing(world, capsys) -> None:
    before = sorted(p for p in world.tmp.rglob("*"))
    assert _run(world) == 0
    assert sorted(p for p in world.tmp.rglob("*")) == before
    assert world.host.owners == {}
    for cmd, _user in world.host.calls:
        assert cmd[0] not in {"useradd", "passwd", "chgrp", "chmod"}
        assert "clone" not in cmd and cmd[:2] != ["systemctl", "enable"]
        assert "daemon-reload" not in cmd
    assert "plan only; nothing changed" in capsys.readouterr().out


# -- apply --------------------------------------------------------------------


def test_every_installed_file_comes_from_github_at_the_sha(world) -> None:
    assert _run(world, "--apply") == 0
    assert sorted(world.host.fetched) == sorted(
        f"{rs.GITHUB_RAW}/{SHA}/{rel}" for rel in rs.SOURCES.values()
    )
    deploy = world.layout.sbin / "core-deploy"
    assert deploy.read_bytes() == _content("infra/core-deploy")
    assert _mode(deploy) == 0o755
    assert world.host.owners[deploy] == ("root", "root")


def test_accounts_are_system_accounts_without_login(world) -> None:
    assert _run(world, "--apply") == 0
    made = [c[0] for c in _ran(world, "useradd")]
    assert [m[-1] for m in made] == ["core-build", "core-sandbox"]
    for m in made:
        assert "--system" in m and "/usr/sbin/nologin" in m
    assert [c[0][-1] for c in _ran(world, "passwd")] == ["core-build", "core-sandbox"]


def test_directories_and_their_modes(world) -> None:
    assert _run(world, "--apply") == 0
    root = world.layout.core_root
    expected = {
        root / "releases": (("root", "root"), 0o755),
        root / "run": (("core", "core"), 0o700),
        root / "etc": (("root", "core"), 0o750),
        root / "build": (("root", "root"), 0o711),
        root / "backups": (("root", "root"), 0o700),
    }
    for path, (owner, mode) in expected.items():
        assert world.host.owners[path] == owner, path
        assert _mode(path) == mode, path


def test_clone_runs_git_only_as_core_sparse_and_at_the_sha(world) -> None:
    assert _run(world, "--apply") == 0
    git = _ran(world, "git")
    assert git and all(user == "core" for _cmd, user in git)
    for cmd, _ in git:
        assert "core.hooksPath=/dev/null" in cmd
    clone = next(cmd for cmd, _ in git if "clone" in cmd)
    assert "https://github.com/DariuszNewecki/CORE.git" in clone
    assert "--no-checkout" in clone
    sparse = next(cmd for cmd, _ in git if "set" in cmd)
    for pattern in ("!/.intent/", "!/.specs/", "!/CLAUDE.md", "!/.claude/"):
        assert pattern in sparse
    assert any(cmd[-2:] == ["--detach", SHA] for cmd, _ in git)
    chmod = next(cmd for cmd, _ in _ran(world, "chmod"))
    assert "g-w" in chmod[2] and chmod[-1].endswith("/repo/.git")
    tmp = world.layout.repo / "var" / "tmp"
    assert _mode(tmp) == 0o751 and _mode(world.layout.repo) == 0o751


def test_configuration_from_the_examples_and_the_dev_secrets(world, capsys) -> None:
    assert _run(world, "--apply") == 0
    etc = world.layout.etc
    assert (etc / "core.env").read_bytes() == CORE_ENV
    assert (etc / "deploy.conf").read_bytes() == _content(
        "infra/systemd/d2/deploy.conf.example"
    )
    assert (etc / "secrets.env").read_bytes() == world.layout.dev_secrets.read_bytes()
    for name, owner in (
        ("core.env", ("core", "core")),
        ("deploy.conf", ("root", "root")),
        ("secrets.env", ("core", "core")),
    ):
        assert _mode(etc / name) == 0o600
        assert world.host.owners[etc / name] == owner
    out = capsys.readouterr().out
    assert "CORE_MASTER_KEY, DATABASE_URL" in out and "postgres://x" not in out


def test_existing_configuration_is_kept(world) -> None:
    etc = world.layout.etc
    etc.mkdir(parents=True)
    (etc / "core.env").write_bytes(
        b"CORE_UPSTREAM_URL=https://github.com/a/b.git\nMINE=1\n"
    )
    (etc / "secrets.env").write_bytes(b"DATABASE_URL=mine\n")
    assert _run(world, "--apply") == 0
    assert b"MINE=1" in (etc / "core.env").read_bytes()
    assert (etc / "secrets.env").read_bytes() == b"DATABASE_URL=mine\n"
    clone = next(cmd for cmd, _ in _ran(world, "git") if "clone" in cmd)
    assert "https://github.com/a/b.git" in clone


def test_missing_secrets_is_a_failure(world) -> None:
    world.layout.dev_secrets.unlink()
    assert _run(world, "--apply") == 1


def test_sandbox_inbox_units_and_socket(world) -> None:
    assert _run(world, "--apply") == 0
    inbox = world.layout.inbox
    assert world.host.owners[inbox] == ("core", "core-sandbox")
    assert _mode(inbox) == 0o2750
    for name in rs.SANDBOX_UNITS:
        path = world.layout.system_units / name
        assert path.read_bytes() == _content(rs.SOURCES[name])
        assert _mode(path) == 0o644
    cmds = [c[0] for c in _ran(world, "systemctl")]
    assert ["systemctl", "daemon-reload"] in cmds
    assert ["systemctl", "enable", "--now", "core-sandbox.socket"] in cmds


def test_service_units_replace_todays_and_keep_the_old_ones(world) -> None:
    assert _run(world, "--apply") == 0
    for name in rs.SERVICE_UNITS:
        assert (world.units / name).read_bytes() == _content(rs.SOURCES[name])
        assert world.host.owners[world.units / name] == ("core", "core")
    saved = world.layout.backups / "units-20261012T080000Z"
    assert (saved / "core-daemon.service").read_text().startswith("ExecStart=/opt/dev")
    assert not (world.units / "core-daemon.service.d" / "env.conf").exists()
    assert (saved / "core-daemon.service.d-env.conf").is_file()
    cmds = [c[0] for c in _ran(world, "systemctl")]
    assert ["systemctl", "--user", "-M", "core@", "daemon-reload"] in cmds
    # Reloaded, never restarted: core-deploy switches and restarts.
    assert not any("restart" in c and "--user" in c for c in cmds)


def test_rerun_is_a_no_op(world, capsys) -> None:
    assert _run(world, "--apply") == 0
    world.host.calls.clear()
    capsys.readouterr()
    assert _run(world, "--apply") == 0
    for cmd, _user in world.host.calls:
        assert cmd[0] not in {"useradd", "passwd"}
        assert "clone" not in cmd and "daemon-reload" not in cmd
        assert cmd[:2] != ["systemctl", "enable"]
    assert "  do: " not in capsys.readouterr().out


def test_done_prints_the_next_commands(world, capsys) -> None:
    assert _run(world, "--apply") == 0
    out = capsys.readouterr().out
    assert f"sudo core-deploy {SHA}" in out
    assert "sandbox-check --mode service" in out


# -- failures that must not pass ---------------------------------------------


def test_an_account_in_another_group_fails(world) -> None:
    world.host.accounts["core-sandbox"] = SimpleNamespace(
        pw_shell="/usr/sbin/nologin", pw_dir="/nonexistent"
    )
    world.host.groups["core-sandbox"] = ["core-sandbox", "core"]
    assert _run(world, "--apply") == 1


def test_a_probe_that_reads_etc_fails(world) -> None:
    world.host.readable_etc_by = {"core-build"}
    assert _run(world, "--apply") == 1
