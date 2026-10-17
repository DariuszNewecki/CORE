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
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import re
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
        self.declared: list[str] | None = list(self.unit_list)
        self.alive = ["sync_db_worker"]
        self.beats_after_switch = True
        self.clock = T0
        self.same_tree = True
        self.setup_diff = b""
        self.law_diff = b""  # git diff --name-status -z output for governed text
        self.law_rc = 0
        self.law_runs: list[dict] = []
        self.governors = ["darek"]
        self.setup_rc = 0
        self.law_setup_rc = 0
        self.setup_runs: list[list[str]] = []
        self.claude_source: dict[str, bytes] = {}  # infra/claude-hooks/<name>

    # -- processes --------------------------------------------------------
    def run(self, cmd, *, user=None, input=None, check=True):
        cmd = list(cmd)
        self.calls.append((user, cmd))
        rc, out = 0, b""
        joined = " ".join(cmd)
        if cmd[0] == "git":
            if "merge-base" in cmd:
                rc = 0 if self.on_develop else 1
            elif "rev-parse" in cmd and cmd[-1].endswith("^{tree}"):
                commit = cmd[-1].split("^")[0]
                out = (b"tree-same" if self.same_tree else commit.encode()) + b"\n"
            elif "rev-parse" in cmd:
                out = SHA.encode() + b"\n"
            elif "archive" in cmd:
                out = _archive(SOURCE)
            elif "ls-tree" in cmd:
                out = b"".join(
                    f"infra/claude-hooks/{n}".encode() + b"\0"
                    for n in self.claude_source
                )
            elif "diff" in cmd and "--name-only" in cmd:
                out = self.setup_diff
            elif "diff" in cmd:
                out = self.law_diff
            elif "show" in cmd and cmd[-1].split(":", 1)[-1].startswith(
                "infra/claude-hooks/"
            ):
                out = self.claude_source[cmd[-1].rsplit("/", 1)[-1]]
            elif "show" in cmd and cmd[-1].split(":", 1)[-1].startswith("infra/core-"):
                out = b"#!/bin/sh\n# " + cmd[-1].encode() + b"\n"
            elif "show" in cmd and cmd[-1].split(":", 1)[-1].startswith(
                (".intent", ".specs")
            ):
                out = b"governed text at " + cmd[-1].encode() + b"\n"
            elif "show" in cmd:
                out = LOCK if cmd[-1].endswith("poetry.lock") else PYPROJECT
            elif "log" in cmd:
                out = b"Dariusz Newecki\n"
        elif "wheel" in cmd and "--wheel-dir" in cmd:
            target = Path(cmd[cmd.index("--wheel-dir") + 1])
            _wheel(
                target / "core_runtime-2.13.0-py3-none-any.whl",
                self.wheel_files,
                self.wheel_scripts,
            )
        elif "apply-merge" in cmd:
            assert cmd[0] == "env" and cmd[1].startswith("--chdir=/")
            assert cmd[2] == "REPO_PATH=" + cmd[1].split("=", 1)[1]
            env_code = cmd[3]
            assert env_code.startswith("CORE_LAW_CODE_TREE=")
            code = Path(env_code.split("=", 1)[1])
            cmd = cmd[4:]
            pdir = Path(cmd[cmd.index("--proposals-dir") + 1]) / cmd[3]
            self.law_runs.append(
                {
                    "user": user,
                    "core_admin": cmd[0],
                    "commit": cmd[cmd.index("--merge-commit") + 1],
                    "merged_by": cmd[cmd.index("--merged-by") + 1],
                    "files": sorted(
                        p.relative_to(pdir / "files").as_posix()
                        for p in (pdir / "files").rglob("*")
                        if p.is_file()
                    ),
                    "proposal_md": (pdir / "proposal.md").read_text(),
                    "code_tree": code,
                    "code_files": {
                        p.relative_to(code).as_posix(): p.read_bytes()
                        for p in code.rglob("*")
                        if p.is_file()
                    },
                }
            )
            rc = self.law_rc
        elif len(cmd) > 1 and "/core-setup-" in cmd[1] and user is None:
            assert Path(cmd[1]).read_bytes().startswith(b"#!/bin/sh")
            self.setup_runs.append([cmd[0], Path(cmd[1]).name, *cmd[2:]])
            rc = self.setup_rc
        elif cmd[0].endswith("sbin/core-law-setup") and user is None:
            self.setup_runs.append(["core-law-setup", *cmd[1:]])
            rc = self.law_setup_rc
        elif cmd[:4] == ["/usr/bin/python3", "-I", "-m", "venv"] and user is None:
            (Path(cmd[4]) / "bin").mkdir(parents=True)
        elif cmd[0] == "systemd-run":
            body = cmd[cmd.index("--") + 1 :]
            if body[-2:] == ["daemon", "units"]:
                rc = 2 if self.declared is None else 0
                out = "\n".join(self.declared or []).encode()
            elif "status" in body:
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

    def group_members(self, group):
        assert group == "core-gov"
        return list(self.governors)

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
    sbin = root / "sbin"
    sbin.mkdir(exist_ok=True)
    # No dev checkout: the host's own /opt/dev/CORE never takes part.
    dev = ["--dev-repo", str(root / "no-dev-checkout")]
    return cd.main(
        [SHA, "--root", str(root), "--sbin", str(sbin), *dev, *extra], host=host
    )


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
    # The hashed wheel and its lock are kept for core-law-setup.
    dist = root / "releases" / SHA / "dist"
    (wheel,) = dist.glob("*.whl")
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == release["wheel_sha256"]
    assert (dist / "poetry.lock").read_bytes() == LOCK
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


def test_units_the_release_declares_are_started_and_enabled_for_boot(
    root: Path,
) -> None:
    # 2026-10-14: after a reboot nothing was enabled; the governor started
    # core-api and core-daemon by hand and the hand deploy restarted only
    # those two, leaving every dedicated worker down.
    _with_previous(root)
    host = FakeHost(root)
    host.unit_list = ["core-api.service", "core-daemon.service"]
    host.declared = [
        "core-daemon.service",
        "core-api.service",
        "core-daemon-worker@sync_db_worker.service",
    ]
    assert _deploy(root, host) == 0
    by_verb = {c[4]: c[5:] for c in host.commands("systemctl")}
    assert set(by_verb["restart"]) == set(host.declared)
    assert set(by_verb["enable"]) == set(host.declared)
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert set(entry["units"]) == set(host.declared)


def test_a_release_without_daemon_units_keeps_the_loaded_units(root: Path) -> None:
    host = FakeHost(root)
    host.declared = None
    assert _deploy(root, host) == 0
    by_verb = {c[4]: c[5:] for c in host.commands("systemctl")}
    assert set(by_verb["restart"]) == set(host.unit_list)


def test_a_failed_switch_enables_nothing(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.health = False
    assert _deploy(root, host) != 0
    assert "enable" not in host.systemctl_verbs()


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


# ID: 200232ef-a954-4a12-bf48-b573b5f887ef
def test_the_release_venv_gets_the_pinned_core_cli_wheel_only(root: Path) -> None:
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    download = [
        (u, c)
        for u, c in host.calls
        if "download" in c and any(a.endswith("core-cli.txt") for a in c)
    ]
    assert len(download) == 1
    user, cmd = download[0]
    assert user == "core-build"  # fetched by the build account, never root
    for flag in ("--no-deps", "--require-hashes", "--only-binary=:all:"):
        assert flag in cmd
    install = [
        (u, c)
        for u, c in host.calls
        if "install" in c and any(a.endswith("core-cli.txt") for a in c)
    ]
    assert len(install) == 1
    user, cmd = install[0]
    assert user is None and cmd[0].endswith(f"releases/{SHA}/venv/bin/python")
    for flag in ("--no-deps", "--require-hashes", "--no-index", "--only-binary=:all:"):
        assert flag in cmd


# ID: fcdd72b8-2f48-4ef5-ad49-879809b0d018
def test_core_cli_pin_is_the_docs_version_with_a_sha256() -> None:
    makefile = (REPO / "Makefile").read_text()
    match = re.search(r"^CORE_CLI_DOCS_VERSION\s*:=\s*(\S+)", makefile, re.M)
    assert match and cd.CORE_CLI == f"core-cli=={match.group(1)}"
    assert re.fullmatch(r"[0-9a-f]{64}", cd.CORE_CLI_SHA256)


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
        [  # the newest run of a check decides: rerun red after green
            {"id": 1, "name": "ci", "status": "completed", "conclusion": "success"},
            {"id": 2, "name": "ci", "status": "completed", "conclusion": "failure"},
        ],
    ],
)
def test_ci_not_green_is_refused(root: Path, runs: list[dict]) -> None:
    host = FakeHost(root)
    host.check_runs = runs
    assert _deploy(root, host) == 1
    assert not (root / "releases" / SHA).exists()


# ID: f0a14dcc-057b-427d-9dd1-74efef48bef0
def test_ci_counts_only_the_newest_run_of_each_check(root: Path) -> None:
    host = FakeHost(root)
    host.check_runs = [
        {
            "id": 1,
            "name": "host-change-stated",
            "status": "completed",
            "conclusion": "failure",
        },
        {
            "id": 2,
            "name": "host-change-stated",
            "status": "completed",
            "conclusion": "success",
        },
    ]
    assert _deploy(root, host) == 0


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


# -- one-path flow: deploy branch and law (governor redesign 2026-10-12) -------

LAW_DIFF = b"M\0.intent/rules/a.json\0D\0.specs/old.md\0"


def test_deploy_branch_comes_from_deploy_conf(root: Path) -> None:
    (root / "etc" / "deploy.conf").write_text("DEPLOY_BRANCH=main\n")
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    fetch = next(c for c in host.commands("git") if "fetch" in c)
    assert "refs/heads/main:refs/remotes/upstream/main" in fetch


def test_changed_law_is_applied_by_core_law_with_the_new_release(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.law_diff = LAW_DIFF
    assert _deploy(root, host, "--merged-by", "darek") == 0
    [run] = host.law_runs
    assert run["user"] == "core-law"
    assert run["core_admin"].endswith(f"releases/{SHA}/venv/bin/core-admin")
    assert run["commit"] == SHA and run["merged_by"] == "darek"
    assert run["files"] == [".intent/rules/a.json"]
    assert "- `.specs/old.md`" in run["proposal_md"]
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert entry["law_applied"] is True and entry["merged_by"] == "darek"


def test_law_is_checked_against_the_code_of_the_target(root: Path) -> None:
    """2026-10-13: 354d17fd was refused because its new worker module was
    looked up in the development checkout; core-law now gets the target's
    tree (by environment variable, so an older release ignores it)."""
    _with_previous(root)
    host = FakeHost(root)
    host.law_diff = LAW_DIFF
    assert _deploy(root, host) == 0
    [run] = host.law_runs
    assert any(c[-2:] == ["--format=tar", SHA] for c in host.commands("git"))
    assert run["code_tree"].is_absolute()
    assert run["code_tree"].parent == root / "build" / f"law-{SHA[:12]}"
    assert run["code_files"] == {**SOURCE, "pyproject.toml": PYPROJECT}
    assert not run["code_tree"].exists()  # removed with the proposal


def test_no_law_change_runs_no_law_apply(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    assert host.law_runs == []


def test_refused_law_stops_before_anything_switches(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.law_diff = LAW_DIFF
    host.law_rc = 1
    assert _deploy(root, host) == 1
    assert _current(root) == OLD
    assert not (root / "releases" / SHA).exists()


def test_switch_back_puts_the_law_back(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.law_diff = LAW_DIFF
    host.inactive = {"core-api.service"}
    assert _deploy(root, host) == 1
    assert _current(root) == OLD
    assert [r["commit"] for r in host.law_runs] == [SHA, OLD]


TESTED = "e" * 40


def test_tested_as_needs_the_same_tree_and_green_ci_on_the_tested_head(
    root: Path,
) -> None:
    host = FakeHost(root)
    assert _deploy(root, host, "--tested-as", TESTED) == 0
    trees = [c for c in host.commands("git") if c[-1].endswith("^{tree}")]
    assert {c[-1] for c in trees} == {f"{SHA}^{{tree}}", f"{TESTED}^{{tree}}"}


def test_tested_as_with_a_different_tree_is_refused(root: Path) -> None:
    host = FakeHost(root)
    host.same_tree = False
    assert _deploy(root, host, "--tested-as", TESTED) == 1
    assert not (root / "releases" / SHA).exists()


# -- self-update and host setup (one-path flow) -----------------------------


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def test_a_deploy_updates_the_host_scripts_from_the_deployed_commit(
    root: Path,
) -> None:
    _with_previous(root)
    (root / "sbin").mkdir()
    (root / "sbin" / "core-pipeline").write_bytes(
        f"#!/bin/sh\n# {SHA}:infra/core-pipeline\n".encode()
    )
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    for name in ("core-deploy", "core-law-setup", "core-sandbox-check"):
        target = root / "sbin" / name
        assert target.read_bytes() == f"#!/bin/sh\n# {SHA}:infra/{name}\n".encode()
        assert _mode(target) == 0o755
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert entry["host_scripts_updated"] == [
        "core-deploy",
        "core-law-setup",
        "core-sandbox-check",
    ]


def _deployer(root: Path, dev: Path) -> cd.Deployer:
    return cd.Deployer(
        FakeHost(root), cd.Layout(root, root / "sbin"), cd.Options(dev_repo=dev)
    )


# ID: 12677f45-5c87-4150-887e-938cf48f9440
def test_claude_md_is_copied_to_the_dev_tree_not_applied_as_law(root: Path) -> None:
    assert "CLAUDE.md" not in cd.GOVERNED_PATHSPECS
    dev = root / "dev"
    dev.mkdir()
    (dev / "CLAUDE.md").write_bytes(b"old\n")
    deployer = _deployer(root, dev)
    assert deployer.update_claude_md(SHA) is True
    target = str(dev / "CLAUDE.md")
    assert deployer.host.calls[-3:] == [
        (None, ["cp", "-T", str(root / ".CLAUDE.md.new"), target]),
        (None, ["chown", "core-law:core-law", target]),
        (None, ["chmod", "0644", target]),
    ]
    assert not (root / ".CLAUDE.md.new").exists()
    (dev / "CLAUDE.md").write_bytes(PYPROJECT)  # FakeHost's `git show` content
    assert deployer.update_claude_md(SHA) is False  # already equal


# ID: 50de6d93-8c03-454e-92e8-88c5711b0f8d
def test_claude_md_is_skipped_without_a_dev_tree(root: Path) -> None:
    assert _deployer(root, root / "absent").update_claude_md(SHA) is False


def test_a_switched_back_deploy_updates_no_host_script(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.inactive = {"core-api.service"}
    assert _deploy(root, host) == 1
    assert not list((root / "sbin").iterdir())


def _ledger(root: Path) -> dict:
    return json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])


def _index(host: FakeHost, predicate) -> int:
    return next(i for i, (_, c) in enumerate(host.calls) if predicate(c))


def test_a_merge_changing_units_runs_core_runtime_setup_before_building(
    root: Path,
) -> None:
    """Governor 2026-10-15: a merge is the only approval; the host setup it
    changes is applied by the deploy, from the deployed commit."""
    _with_previous(root)
    host = FakeHost(root)
    host.setup_diff = b"infra/systemd/d2/core-api.service\n"
    assert _deploy(root, host) == 0
    assert host.setup_runs == [
        [
            "/usr/bin/python3",
            "core-runtime-setup",
            "--ref",
            SHA,
            "--governor",
            "darek",
            "--apply",
        ]
    ]
    setup = _index(host, lambda c: len(c) > 1 and "/core-setup-" in c[1])
    build = _index(host, lambda c: "--wheel-dir" in c)
    assert setup < build
    assert not Path(host.calls[setup][1][1]).parent.exists()  # temp copy removed
    assert _ledger(root)["host_setup"] == ["core-runtime-setup"]
    assert _current(root) == SHA


def test_a_merge_changing_the_one_path_setup_runs_it(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.setup_diff = b"infra/core-one-path-setup\n"
    assert _deploy(root, host) == 0
    assert host.setup_runs == [["/bin/bash", "core-one-path-setup", "--ref", SHA]]


def test_a_failed_host_setup_refuses_before_anything_is_built(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.setup_diff = b"infra/core-runtime-setup\n"
    host.setup_rc = 1
    assert _deploy(root, host) == 1
    assert "host setup core-runtime-setup failed" in capsys.readouterr().err
    assert not host.commands("pip") and not any(
        "--wheel-dir" in c for _, c in host.calls
    )
    assert not (root / "releases" / SHA).exists()
    assert _current(root) == OLD


@pytest.mark.parametrize("governors", [[], ["darek", "other"]])
def test_host_setup_needs_exactly_one_governor(
    root: Path, governors: list[str]
) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.setup_diff = b"infra/systemd/sandbox/core-sandbox.socket\n"
    host.governors = governors
    assert _deploy(root, host) == 1
    assert host.setup_runs == []
    assert _current(root) == OLD


def test_a_merge_changing_core_law_setup_runs_it_after_the_switch(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.setup_diff = b"infra/core-law-setup\n"
    assert _deploy(root, host) == 0
    assert host.setup_runs == [["core-law-setup", "--governor", "darek", "--apply"]]
    law_setup = _index(host, lambda c: c[0].endswith("sbin/core-law-setup"))
    restart = _index(host, lambda c: c[0] == "systemctl" and c[4] == "restart")
    assert restart < law_setup
    entry = _ledger(root)
    assert (entry["host_setup"], entry["law_setup"]) == ([], "applied")


def test_a_failed_core_law_setup_does_not_undo_the_deploy(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.setup_diff = b"infra/core-law-setup\n"
    host.law_setup_rc = 1
    assert _deploy(root, host) == 0
    assert _current(root) == SHA
    assert _ledger(root)["law_setup"] == "failed"


def test_no_host_setup_change_runs_no_setup(root: Path) -> None:
    _with_previous(root)
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    assert host.setup_runs == []
    assert _ledger(root)["law_setup"] is None


def test_the_host_setup_applied_option_is_gone(root: Path) -> None:
    with pytest.raises(SystemExit):
        _deploy(root, FakeHost(root), "--host-setup-applied")


# -- the assistant's .claude/ from infra/claude-hooks/ -----------------------


def _dev_with_claude(root: Path) -> Path:
    dev = root / "dev"
    hooks = dev / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (dev / ".claude" / "settings.json").write_bytes(b'{"old": 1}\n')
    (hooks / "core-verdict.sh").write_bytes(b"verdict\n")
    (hooks / "core-develop-ancestry.sh").write_bytes(b"ancestry\n")
    return dev


def test_claude_is_made_equal_to_infra_claude_hooks_through_core_law(
    root: Path,
) -> None:
    _with_previous(root)
    dev = _dev_with_claude(root)
    host = FakeHost(root)
    host.claude_source = {
        "settings.json": b'{"new": 1}\n',
        "core-verdict.sh": b"verdict\n",  # equal: not written
        "core-chat-length.sh": b"length\n",
    }
    assert _deploy(root, host, "--dev-repo", str(dev)) == 0
    [run] = host.law_runs
    assert run["user"] == "core-law"
    assert run["files"] == [
        ".claude/hooks/core-chat-length.sh",
        ".claude/settings.json",
    ]
    assert "- `.claude/hooks/core-develop-ancestry.sh`" in run["proposal_md"]
    assert _ledger(root)["law_applied"] is True


def test_claude_already_equal_applies_nothing(root: Path) -> None:
    _with_previous(root)
    dev = _dev_with_claude(root)
    (dev / ".claude" / "hooks" / "core-develop-ancestry.sh").unlink()
    host = FakeHost(root)
    host.claude_source = {
        "settings.json": b'{"old": 1}\n',
        "core-verdict.sh": b"verdict\n",
    }
    assert _deploy(root, host, "--dev-repo", str(dev)) == 0
    assert host.law_runs == []


def test_a_source_without_settings_leaves_claude_alone(root: Path) -> None:
    """Commits before the source held settings.json do not define the set: a
    rollback to one must not strip hooks the installed settings still name."""
    _with_previous(root)
    dev = _dev_with_claude(root)
    host = FakeHost(root)
    host.claude_source = {"core-verdict.sh": b"older verdict\n"}
    assert _deploy(root, host, "--dev-repo", str(dev)) == 0
    assert host.law_runs == []


# -- 8a. the dev checkout follows the deploy (#1063) ----------------------------


class DevGitHost(FakeHost):
    """FakeHost whose git in the dev checkout is real git (the account ignored)."""

    def __init__(self, root: Path, dev: Path) -> None:
        super().__init__(root)
        self.dev = dev

    def run(self, cmd, *, user=None, input=None, check=True):
        if cmd[:3] != ["git", "-C", str(self.dev)]:
            return super().run(cmd, user=user, input=input, check=check)
        self.calls.append((user, list(cmd)))
        result = subprocess.run(cmd, input=input, capture_output=True)
        if check and result.returncode:
            raise cd.Refused(result.stderr.decode())
        return result


def _git(dev: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(dev), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _dev_checkout(tmp_path: Path) -> tuple[Path, str, str]:
    """A dev checkout at commit A; commit B changes code and governed text."""
    dev = tmp_path / "dev"
    (dev / "src").mkdir(parents=True)
    (dev / ".intent").mkdir()
    _git(dev.parent, "init", "-q", "-b", "main", str(dev))
    _git(dev, "config", "user.email", "t@example.com")
    _git(dev, "config", "user.name", "t")
    (dev / "src" / "a.py").write_text("a = 1\n")
    (dev / ".intent" / "rule.yaml").write_text("v: 1\n")
    _git(dev, "add", "-A")
    _git(dev, "commit", "-q", "-m", "A")
    a = _git(dev, "rev-parse", "HEAD")
    (dev / "src" / "a.py").write_text("a = 2\n")
    (dev / "src" / "b.py").write_text("b = 1\n")
    (dev / ".intent" / "rule.yaml").write_text("v: 2\n")
    _git(dev, "add", "-A")
    _git(dev, "commit", "-q", "-m", "B")
    b = _git(dev, "rev-parse", "HEAD")
    _git(dev, "reset", "-q", "--hard", a)
    return dev, a, b


def _follower(root: Path, dev: Path) -> cd.Deployer:
    return cd.Deployer(
        DevGitHost(root, dev), cd.Layout(root, root / "sbin"), cd.Options(dev_repo=dev)
    )


def test_the_dev_checkout_follows_the_deploy_once_its_law_is_applied(
    root: Path, tmp_path: Path
) -> None:
    dev, _a, b = _dev_checkout(tmp_path)
    (dev / ".intent" / "rule.yaml").write_text("v: 2\n")  # core-law applied it
    (dev / "notes.txt").write_text("someone's untracked file\n")
    deployer = _follower(root, dev)

    assert deployer.follow_dev_checkout(b) == f"moved {_a[:12]} -> {b[:12]}"
    assert _git(dev, "rev-parse", "HEAD") == b
    assert _git(dev, "status", "--porcelain") == "?? notes.txt"
    assert (dev / "src" / "b.py").read_text() == "b = 1\n"
    # git ran as the owner of the working files, never as root.
    dev_git = [u for u, c in deployer.host.calls if c[:3] == ["git", "-C", str(dev)]]
    assert dev_git and set(dev_git) == {"core-claude"}
    assert deployer.follow_dev_checkout(b) is None  # already there


def test_the_dev_checkout_stays_while_its_governed_text_differs(
    root: Path, tmp_path: Path
) -> None:
    dev, a, b = _dev_checkout(tmp_path)  # .intent/rule.yaml still at A
    assert _follower(root, dev).follow_dev_checkout(b) == (
        "not moved: governed text differs"
    )
    assert _git(dev, "rev-parse", "HEAD") == a
    assert (dev / "src" / "a.py").read_text() == "a = 1\n"


def test_the_dev_checkout_is_not_moved_back_or_over_local_work(
    root: Path, tmp_path: Path
) -> None:
    dev, a, b = _dev_checkout(tmp_path)
    (dev / ".intent" / "rule.yaml").write_text("v: 2\n")
    (dev / "src" / "b.py").write_text("untracked work\n")  # B would overwrite it
    deployer = _follower(root, dev)
    assert deployer.follow_dev_checkout(b) == "not moved: git refused"
    assert _git(dev, "rev-parse", "HEAD") == a
    assert (dev / "src" / "b.py").read_text() == "untracked work\n"

    (dev / "src" / "b.py").unlink()
    assert deployer.follow_dev_checkout(b).startswith("moved")
    # A rollback deploys an older commit: the checkout stays where it is.
    assert deployer.follow_dev_checkout(a) == "not moved: not behind"
    assert _git(dev, "rev-parse", "HEAD") == b


def test_without_a_dev_checkout_nothing_is_done(root: Path) -> None:
    assert _deployer(root, root / "absent").follow_dev_checkout(SHA) is None
