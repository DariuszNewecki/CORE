"""core-deploy (ADR-132 D10 · D2, C6): the governor's act that makes a commit run.

The real script is loaded and driven against a fake root (a temporary
directory laid out like /opt/core) with a scripted Host: every process,
HTTP call and sleep goes through it, so these tests prove the control flow
— which account runs what, what is refused before anything live changes,
when a failure switches back and when it stops for the governor — without
root, systemd, git or a network. The wheel-integrity and lock-pinning
helpers run for real on real archives, wheels and lock text.
"""

from __future__ import annotations

import datetime
import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "infra" / "core-deploy"
SHA = "a" * 40
OLD = "b" * 40
T0 = datetime.datetime(2026, 10, 11, 12, 0, tzinfo=datetime.UTC)


def _load() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("core_deploy", str(SCRIPT))
    spec = importlib.util.spec_from_loader("core_deploy", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["core_deploy"] = module  # dataclasses resolve the module by name
    loader.exec_module(module)
    return module


cd = _load()

PYPROJECT = b'[project]\nname = "core-runtime"\n[project.scripts]\ncore-admin = "cli.admin_cli:app"\n'
SOURCE = {"src/cli/admin_cli.py": b"app = None\n", "src/shared/x.py": b"X = 1\n"}
LOCK = b"""
[[package]]
name = "fastapi"
version = "0.136.1"
groups = ["main"]
files = [
    {file = "fastapi-0.136.1-py3-none-any.whl", hash = "sha256:aaa"},
    {file = "fastapi-0.136.1.tar.gz", hash = "sha256:bbb"},
]

[[package]]
name = "colorama"
version = "0.4.6"
groups = ["dev"]
markers = "sys_platform == \\"win32\\""
files = [{file = "colorama-0.4.6-py2.py3-none-any.whl", hash = "sha256:ccc"}]
"""


def _archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, body in {**files, "pyproject.toml": PYPROJECT}.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def _wheel(
    path: Path, files: dict[str, bytes], scripts: str = "core-admin = cli.admin_cli:app"
) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
        zf.writestr("core_runtime-2.13.0.dist-info/METADATA", "Name: core-runtime\n")
        zf.writestr(
            "core_runtime-2.13.0.dist-info/entry_points.txt",
            f"[console_scripts]\n{scripts}\n",
        )


GOOD_WHEEL = {"cli/admin_cli.py": b"app = None\n", "shared/x.py": b"X = 1\n"}


class FakeHost(cd.Host):
    """Scripted host. Knobs are attributes; every call is recorded."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[tuple[str | None, list[str]]] = []
        self.on_develop = True
        self.check_runs = [
            {"name": "ci", "status": "completed", "conclusion": "success"}
        ]
        self.wheel_files = dict(GOOD_WHEEL)
        self.wheel_scripts = "core-admin = cli.admin_cli:app"
        self.status = {
            "connected": True,
            "pending_migrations": [],
            "probe_failures": [],
        }
        self.status_after_migrate = {
            "connected": True,
            "pending_migrations": [],
            "probe_failures": [],
        }
        self.migrated = False
        self.migrate_rc = 0
        self.backup_ok = True
        self.health = True
        self.new_health = True
        self.inactive: set[str] = set()
        self.unit_list = [
            "core-api.service",
            "core-daemon.service",
            "core-daemon-worker@sync_db_worker.service",
        ]
        self.wanted: list[str] = []
        self.alive = ["sync_db_worker"]
        self.beats_after_switch = True
        self.clock = T0

    # -- processes --------------------------------------------------------
    def run(self, cmd, *, user=None, input=None, check=True):
        cmd = list(cmd)
        self.calls.append((user, cmd))
        rc, out = 0, b""
        joined = " ".join(cmd)
        if cmd[0] == "git":
            if "merge-base" in cmd:
                rc = 0 if self.on_develop else 1
            elif "rev-parse" in cmd:
                out = SHA.encode() + b"\n"
            elif "archive" in cmd:
                out = _archive(SOURCE)
            elif "show" in cmd:
                out = LOCK if cmd[-1].endswith("poetry.lock") else PYPROJECT
        elif "wheel" in cmd and "--wheel-dir" in cmd:
            target = Path(cmd[cmd.index("--wheel-dir") + 1])
            _wheel(
                target / "core_runtime-2.13.0-py3-none-any.whl",
                self.wheel_files,
                self.wheel_scripts,
            )
        elif cmd[:4] == ["/usr/bin/python3", "-I", "-m", "venv"] and user is None:
            (Path(cmd[4]) / "bin").mkdir(parents=True)
        elif cmd[0] == "systemd-run":
            body = cmd[cmd.index("--") + 1 :]
            if "status" in body:
                out = json.dumps(
                    self.status_after_migrate if self.migrated else self.status
                ).encode()
            elif "migrate" in body:
                rc = self.migrate_rc
                self.migrated = rc == 0
        elif cmd[0] == "systemctl":
            verb = cmd[4]
            if verb == "list-units":
                out = "\n".join(
                    f"{u} loaded active running x" for u in self.unit_list
                ).encode()
            elif verb == "show" and cmd[5] == "default.target":
                out = " ".join(["basic.target", *self.wanted]).encode()
            elif verb == "is-active":
                rc = 1 if cmd[5] in self.inactive else 0
        elif cmd[:2] == ["/bin/sh", "-c"]:
            if self.backup_ok:
                out_path = Path(joined.split("> ")[-1])
                out_path.write_bytes(b"dump")
            else:
                rc = 1
        result = subprocess.CompletedProcess(cmd, rc, out, b"")
        if check and rc != 0:
            raise cd.Refused(f"command failed ({rc}): {joined}")
        return result

    # -- network / time -----------------------------------------------------
    def http_json(self, url, timeout=15.0):
        if "check-runs" in url:
            return {"check_runs": self.check_runs}
        if url.endswith(":8765/health"):
            if not self.new_health:
                raise OSError("connection refused")
            return {"status": "ok"}
        if url.endswith("/health"):
            if not self.health:
                raise OSError("connection refused")
            return {"status": "ok"}
        if url.endswith("/v1/daemon/status"):
            beat = self.clock + datetime.timedelta(
                seconds=5 if self.beats_after_switch else -60
            )
            return {
                "workers": [
                    {"name": n, "alive": True, "last_heartbeat": beat.isoformat()}
                    for n in self.alive
                ]
            }
        raise AssertionError(url)

    def now(self):
        return self.clock

    def sleep(self, seconds):
        pass

    def chown(self, path, user, recursive=False):
        self.calls.append((None, ["chown-py", user, str(path)]))

    # -- queries ----------------------------------------------------------------
    def commands(self, first: str) -> list[list[str]]:
        return [c for _, c in self.calls if c and c[0] == first]

    def systemctl_verbs(self) -> list[str]:
        return [c[4] for c in self.commands("systemctl")]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "opt-core"
    (r / "etc").mkdir(parents=True)
    (r / "releases").mkdir()
    (r / "etc" / "core.env").write_text(
        "REPO_PATH=/opt/core/repo\nCORE_UPSTREAM_URL=https://github.com/DariuszNewecki/CORE.git\n"
    )
    return r


def _with_previous(root: Path) -> None:
    (root / "releases" / OLD / "venv").mkdir(parents=True)
    (root / "current").symlink_to(Path("releases") / OLD)


def _deploy(root: Path, host: FakeHost, *extra: str) -> int:
    return cd.main([SHA, "--root", str(root), *extra], host=host)


def _current(root: Path) -> str | None:
    link = root / "current"
    return Path(link.readlink()).name if link.is_symlink() else None


# ID: d49ff65f-a7e0-46ba-b49f-d674ca956abb
def test_happy_path_installs_switches_verifies_and_records(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    assert _deploy(root, host) == 0

    release = json.loads(
        (root / "releases" / SHA / "venv" / "core-release.json").read_text()
    )
    assert release["sha"] == SHA and len(release["wheel_sha256"]) == 64  # C4 contract
    assert _current(root) == SHA
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert entry["action"] == "deploy" and entry["previous"] == OLD
    assert entry["migrations_applied"] == [] and entry["sha"] == SHA
    assert "restart" in host.systemctl_verbs()
    assert not (root / "build" / SHA).exists()


# ID: 83e4a3c5-0176-4965-a5a0-3ee2ab1fdfd7
def test_first_deploy_with_nothing_loaded_starts_the_enabled_units(root: Path) -> None:
    # 2026-10-12: no unit was loaded, so the first deploy restarted nothing
    # and refused ("API /health did not answer; no previous release").
    host = FakeHost(root)
    host.wanted = list(host.unit_list)
    host.unit_list = []
    assert _deploy(root, host) == 0
    restart = next(c for c in host.commands("systemctl") if c[4] == "restart")
    assert set(restart[5:]) == set(host.wanted)
    assert _current(root) == SHA


# ID: 4084c0c0-0029-4b7c-978a-ca94240f1cf8
def test_each_step_runs_as_its_account(root: Path) -> None:
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    by_user = {}
    for user, cmd in host.calls:
        by_user.setdefault(cmd[0], set()).add(user)
    assert by_user["git"] == {"core"}  # CORE's own clone, never the dev tree
    assert by_user["tar"] == {"core-build"}
    pip_build = [
        u for u, c in host.calls if "pip" in c[0] and ("wheel" in c or "download" in c)
    ]
    assert pip_build and set(pip_build) == {
        "core-build"
    }  # build backends never as root
    installs = [(u, c) for u, c in host.calls if "install" in c]
    assert installs and all(u is None for u, _ in installs)  # root installs wheels only
    assert all("--no-index" in c for _, c in installs)
    assert any("--require-hashes" in c for _, c in installs)
    assert all(
        c[c.index("--") + 1 :][0].endswith("venv/bin/python")
        for c in host.commands("systemd-run")
    )
    assert all(SAFE in host.commands("git")[0] for SAFE in cd.SAFE_GIT)


# ID: 9d035205-09eb-4efa-9137-437d94d6afe8
def test_not_on_upstream_develop_is_refused_before_building(root: Path) -> None:
    host = FakeHost(root)
    host.on_develop = False
    assert _deploy(root, host) == 1
    assert not (root / "releases" / SHA).exists()
    assert host.commands("tar") == [] and host.commands("systemctl") == []


# ID: 16345744-c8cd-487f-b06a-3119007922f3
@pytest.mark.parametrize(
    "runs",
    [
        [],
        [{"name": "ci", "status": "completed", "conclusion": "failure"}],
        [{"name": "ci", "status": "in_progress", "conclusion": None}],
    ],
)
def test_ci_not_green_is_refused(root: Path, runs: list[dict]) -> None:
    host = FakeHost(root)
    host.check_runs = runs
    assert _deploy(root, host) == 1
    assert not (root / "releases" / SHA).exists()


# ID: 04bff2ec-7d3c-46fe-acb3-498768f7b56f
def test_existing_release_is_refused(root: Path) -> None:
    (root / "releases" / SHA).mkdir()
    host = FakeHost(root)
    assert _deploy(root, host) == 1
    assert host.commands("tar") == []


# ID: ce4e9849-add9-43d8-aafe-7a3df252da7f
@pytest.mark.parametrize(
    ("files", "scripts"),
    [
        ({**GOOD_WHEEL, "shared/x.py": b"X = 2\n"}, "core-admin = cli.admin_cli:app"),
        (
            {**GOOD_WHEEL, "shared/extra.py": b"evil()\n"},
            "core-admin = cli.admin_cli:app",
        ),
        ({**GOOD_WHEEL, "zz.pth": b"import evil\n"}, "core-admin = cli.admin_cli:app"),
        (GOOD_WHEEL, "core-admin = evil:main"),
    ],
    ids=["changed-bytes", "extra-file", "pth", "console-script"],
)
def test_wheel_not_matching_source_is_refused(
    root: Path, files: dict, scripts: str
) -> None:
    host = FakeHost(root)
    host.wheel_files, host.wheel_scripts = files, scripts
    assert _deploy(root, host) == 1
    assert not (root / "releases" / SHA).exists()
    assert not [c for u, c in host.calls if u is None and "install" in c]


# ID: 3d67a682-ac11-4fc0-9e64-f4ba97ffcdaa
def test_pending_migrations_without_flag_refuse_and_leave_no_release(
    root: Path,
) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    assert _deploy(root, host) == 1
    assert _current(root) == OLD
    assert not (
        root / "releases" / SHA
    ).exists()  # a corrected re-run can install again
    assert "stop" not in host.systemctl_verbs()


# ID: 5c0c3f29-cd6f-4324-a9fe-39eb85bb0885
def test_migrate_without_backup_command_refuses_before_stopping(root: Path) -> None:
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    assert _deploy(root, host, "--migrate") == 1
    assert "stop" not in host.systemctl_verbs()


# ID: 493246ca-55cf-4d8c-9d6e-7790bc1f02ce
def test_migration_happy_path_backs_up_then_migrates_and_records(root: Path) -> None:
    (root / "etc" / "deploy.conf").write_text("BACKUP_COMMAND=pg_dump x > {out}\n")
    _with_previous(root)
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    assert _deploy(root, host, "--migrate") == 0
    verbs = host.systemctl_verbs()
    assert verbs.index("stop") < verbs.index("restart")
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert entry["migrations_applied"] == ["20261011_x.sql"]
    assert Path(entry["backup"]).read_bytes() == b"dump"


# ID: 34dfc2bc-e5f0-4de8-b711-a4569983ca55
def test_failed_migration_stops_for_the_governor_and_never_restarts_old(
    root: Path,
) -> None:
    (root / "etc" / "deploy.conf").write_text("BACKUP_COMMAND=pg_dump x > {out}\n")
    _with_previous(root)
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    host.migrate_rc = 1
    assert _deploy(root, host, "--migrate") == 3
    assert _current(root) == OLD
    verbs = host.systemctl_verbs()
    assert "stop" in verbs and "restart" not in verbs and "start" not in verbs
    assert (root / "releases" / SHA).exists()  # kept: fixing forward is a choice


# ID: 3cdcb684-31f2-41a6-8db4-4b43c1b625ff
def test_failed_backup_restarts_units_and_migrates_nothing(root: Path) -> None:
    (root / "etc" / "deploy.conf").write_text("BACKUP_COMMAND=pg_dump x > {out}\n")
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    host.backup_ok = False
    assert _deploy(root, host, "--migrate") == 1
    assert "start" in host.systemctl_verbs()
    assert not any("migrate" in c for c in host.commands("systemd-run"))


# ID: ee3fa739-9ace-4edc-b742-0aaad3d57a39
def test_readiness_failure_without_migration_changes_nothing(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.new_health = False
    assert _deploy(root, host) == 1
    assert _current(root) == OLD
    assert "restart" not in host.systemctl_verbs()
    assert not (root / "releases" / SHA).exists()


# ID: 94fb0a14-2b32-4fa6-baa8-ac8daf807234
def test_unit_failure_after_switch_switches_back(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.inactive = {"core-daemon.service"}
    assert _deploy(root, host) == 1
    assert _current(root) == OLD
    assert host.systemctl_verbs().count("restart") == 2  # new, then back to old
    assert not (root / "deploy-ledger.jsonl").exists()


# ID: cb4a1d10-3b47-4ea6-b42f-a8f56d437627
def test_missing_heartbeat_after_switch_switches_back(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.beats_after_switch = False
    host.health = True
    assert _deploy(root, host) == 1
    assert _current(root) == OLD


# ID: db579055-a4f9-4973-87f9-03dadfa0c4dd
def test_rollback_refuses_across_a_migration(root: Path) -> None:
    _with_previous(root)
    (root / "releases" / SHA / "venv").mkdir(parents=True)
    (root / "current").unlink()
    (root / "current").symlink_to(Path("releases") / SHA)
    (root / "deploy-ledger.jsonl").write_text(
        json.dumps(
            {
                "action": "deploy",
                "sha": SHA,
                "previous": OLD,
                "migrations_applied": ["m.sql"],
                "backup": "/b",
            }
        )
        + "\n"
    )
    host = FakeHost(root)
    assert cd.main(["--rollback", "--root", str(root)], host=host) == 1
    assert _current(root) == SHA
    assert "restart" not in host.systemctl_verbs()


# ID: b4bbf67b-83aa-4042-b1b7-fa5459d5b9a8
def test_rollback_switches_to_previous_and_records(root: Path) -> None:
    _with_previous(root)
    (root / "releases" / SHA / "venv").mkdir(parents=True)
    (root / "current").unlink()
    (root / "current").symlink_to(Path("releases") / SHA)
    (root / "deploy-ledger.jsonl").write_text(
        json.dumps(
            {"action": "deploy", "sha": SHA, "previous": OLD, "migrations_applied": []}
        )
        + "\n"
    )
    host = FakeHost(root)
    assert cd.main(["--rollback", "--root", str(root)], host=host) == 0
    assert _current(root) == OLD
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert entry["action"] == "rollback" and entry["sha"] == OLD


# ID: 0972bd76-ee9e-4079-8cb4-5a8edfafc6c9
def test_lock_requirements_pin_every_file_hash_and_keep_markers() -> None:
    text = cd.requirements_from_lock(LOCK)
    assert (
        "fastapi==0.136.1" in text
        and "--hash=sha256:aaa" in text
        and "--hash=sha256:bbb" in text
    )
    assert (
        'colorama==0.4.6 ; sys_platform == "win32"' in text
    )  # dev group included, marker kept


# ID: 1d8e8e40-41d5-4d87-b29a-b44ea19bf2ed
def test_lock_package_without_hashes_is_refused() -> None:
    with pytest.raises(cd.Refused):
        cd.requirements_from_lock(
            b'[[package]]\nname = "x"\nversion = "1"\nfiles = []\n'
        )


# ID: b64c6101-f10b-4ec2-83b7-126ba5f6aaff
@pytest.mark.parametrize("ref", ["-c", "a..b", "--upload-pack=x", ""])
def test_unsafe_refs_are_rejected(ref: str) -> None:
    assert not cd.valid_ref(ref)


# ID: 9f3fa94a-1b15-47db-a03d-1f33016913dd
def test_runuser_gets_a_clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(cd.subprocess, "run", fake_run)
    cd.Host().run(["git", "status"], user="root")
    argv = seen["argv"]
    assert argv[:6] == ["runuser", "-u", "root", "--", "env", "-i"]
    assert "HOME=/root" in argv and argv[-2:] == ["git", "status"]


# ID: c73a1916-5883-4769-a85d-b2038d7f6260
def test_refuses_without_root_when_not_under_test(
    monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
    monkeypatch.setattr(cd.os, "geteuid", lambda: 1001)
    assert cd.main([SHA, "--root", str(root)]) == 1
