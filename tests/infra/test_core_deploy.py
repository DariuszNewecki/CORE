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
import os
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
PROMOTION = 1200
GOVERNOR = "DariuszNewecki"


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
        self.required = [{"context": "ci"}]  # GitHub's rules for the branch
        self.rules_url: str | None = None
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
        # The pre-migration dump's restore check (#1113).
        self.list_rc = 0
        self.live_rows = {"core.a": 3, "core.b": 0}
        self.restored_rows: dict[str, int] | None = None  # None: same as live
        self.restore_rc = 0
        self.live_inputs: list[bytes] = []
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
        # The promotion the governor approved (ADR-171).
        self.promotion = {
            "state": "open",
            "base": {"ref": "live"},
            "head": {"ref": "promote/2026-10-19", "sha": SHA},
        }
        self.reviews = [
            {"user": {"login": GOVERNOR}, "state": "APPROVED", "commit_id": SHA}
        ]
        # The reviews from the second read on (after the build), when set.
        self.reviews_later: list | None = None
        self.review_reads = 0
        self.procs: list[str] = []  # /proc/*/maps and cmdline texts
        self.procs_error: Exception | None = None

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
        elif cmd[0] == "pg_restore" and cmd[1] == "--list":
            rc = self.list_rc
            if rc == 0:
                out = b";\n; Archive created\n;\n3; 2615 2200 SCHEMA - core x\n"
        elif cmd[:2] == ["/bin/sh", "-c"] and "docker run" in cmd[2]:
            rc = self.restore_rc
            rows = self.live_rows if self.restored_rows is None else self.restored_rows
            if rc == 0:
                out = "".join(f"{t}|{n}\n" for t, n in rows.items()).encode()
        elif cmd[:2] == ["/bin/sh", "-c"] and "psql" in cmd[2]:
            self.live_inputs.append(input or b"")
            out = "".join(f"{t}|{n}\n" for t, n in self.live_rows.items()).encode()
        elif cmd[:2] == ["docker", "rm"]:
            rc = 1
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
        if "/rules/branches/" in url:
            self.rules_url = url
            if isinstance(self.required, Exception):
                raise self.required
            return [
                {"type": "deletion"},
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": self.required},
                },
            ]
        if url.endswith(f"/pulls/{PROMOTION}/reviews?per_page=100"):
            self.review_reads += 1
            if self.reviews_later is not None and self.review_reads > 1:
                return self.reviews_later
            return self.reviews
        if url.endswith(f"/pulls/{PROMOTION}"):
            return self.promotion
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

    def process_texts(self):
        if self.procs_error:
            raise self.procs_error
        return list(self.procs)

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
    law = ["--law-venv", str(root / "law-venv")]
    conf = root / "pipeline.conf"
    if not conf.exists():
        conf.write_text(f"GOVERNOR_GITHUB={GOVERNOR}\n")
    promotion = [] if "--promotion" in extra else ["--promotion", str(PROMOTION)]
    argv = [SHA, "--root", str(root), "--sbin", str(sbin), *dev, *law, *extra]
    return cd.main([*argv, *promotion, "--pipeline-conf", str(conf)], host=host)


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
        {"id": 1, "name": "ci", "status": "completed", "conclusion": "failure"},
        {"id": 2, "name": "ci", "status": "completed", "conclusion": "success"},
    ]
    assert _deploy(root, host) == 0


def _check(name: str, conclusion: str = "success", app: int = 15368) -> dict:
    return {
        "id": 1,
        "name": name,
        "app": {"id": app},
        "status": "completed",
        "conclusion": conclusion,
    }


MAIN_CHECKS = [  # main's ruleset (main-checks), as GitHub lists it
    {"context": "Static checks", "integration_id": 15368},
    {"context": "Hermetic tests", "integration_id": 15368},
    {"context": "host-change-stated", "integration_id": 15368},
]


# ID: d455a3d9-4e89-4aab-acda-0e828035cc86
def test_a_sha_with_one_required_check_missing_is_refused(root: Path, capsys) -> None:
    # F5: every check that ran is green, but one the rules require never ran.
    host = FakeHost(root)
    host.required = MAIN_CHECKS
    host.check_runs = [_check("Static checks")]
    assert _deploy(root, host) == cd.EX_REFUSED
    assert not (root / "releases" / SHA).exists()
    assert "Hermetic tests: missing" in capsys.readouterr().err
    assert host.rules_url is not None and host.rules_url.startswith(
        "https://api.github.com/repos/DariuszNewecki/CORE/rules/branches/develop"
    )


# ID: 03b9a3f6-9f16-4d78-893e-a45b616ebdab
def test_every_required_check_green_deploys(root: Path) -> None:
    # host-change-stated runs only on pull requests: a main commit has none.
    host = FakeHost(root)
    host.required = MAIN_CHECKS
    host.check_runs = [
        _check("Static checks"),
        _check("Hermetic tests"),
        _check("docs", "success", app=99),  # not required, green
    ]
    assert _deploy(root, host) == 0


# ID: db40fc27-9444-4273-8745-47eebdc4ee6a
@pytest.mark.parametrize(
    "runs, required",
    [
        ([_check("Static checks", app=99)], MAIN_CHECKS[:1]),  # another app
        ([_check("Static checks", "failure")], MAIN_CHECKS[:1]),
        ([_check("Static checks")], []),  # the rules require nothing
        ([_check("Static checks")], [{"context": "host-change-stated"}]),
        ([_check("Static checks")], OSError("rate limited")),
        (  # a red check that is not required still refuses
            [_check("Static checks"), _check("docs", "failure")],
            MAIN_CHECKS[:1],
        ),
        # review finding F1: a skipped required job tested nothing
        ([_check("Static checks", "skipped")], MAIN_CHECKS[:1]),
        ([_check("Static checks", "neutral")], MAIN_CHECKS[:1]),
    ],
    ids=[
        "other-app",
        "red",
        "none",
        "pr-only",
        "unreadable",
        "other-red",
        "skipped",
        "neutral",
    ],
)
def test_required_checks_not_met_are_refused(
    root: Path, runs: list[dict], required: object
) -> None:
    host = FakeHost(root)
    host.check_runs, host.required = runs, required
    assert _deploy(root, host) == cd.EX_REFUSED
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


# ID: 19167f6b-6e84-4ebb-bc0e-6dfa199c0f98
def test_pending_migrations_apply_without_the_migrate_flag(root: Path) -> None:
    # #1255 item 6: the refusal without --migrate never blocked (the
    # pipeline always passed it); the backup and its check still guard.
    (root / "etc" / "deploy.conf").write_text("BACKUP_COMMAND=pg_dump x > {out}\n")
    _with_previous(root)
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    assert _deploy(root, host) == 0
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


CHECKED_CONF = (
    "BACKUP_COMMAND=pg_dump x > {out}\n"
    "PSQL_COMMAND=docker exec -i db psql -U u -d core\n"
    "RESTORE_IMAGE=postgres:16\n"
)


def _migrating(root: Path, conf: str = CHECKED_CONF) -> FakeHost:
    (root / "etc" / "deploy.conf").write_text(conf)
    _with_previous(root)
    host = FakeHost(root)
    host.status = {
        "connected": True,
        "pending_migrations": ["20261011_x.sql"],
        "probe_failures": [],
    }
    return host


def _check_record(root: Path) -> dict:
    (record,) = (root / "backups").glob("*.dump.check.json")
    return json.loads(record.read_text())


def _migrate_ran(host: FakeHost) -> bool:
    return any("migrate" in c for c in host.commands("systemd-run"))


# ID: eaca523d-aec9-406a-a946-b6862582dc22
def test_restore_check_passes_and_records_dump_time_counts(root: Path) -> None:
    """#1113: the dump is listed, restored into a throwaway container (no
    network, the server's image) and its row counts equal the live ones,
    counted read-only; the ledger line carries the result."""
    host = _migrating(root)
    assert _deploy(root, host, "--migrate") == 0
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    check = entry["backup_check"]
    assert check["verdict"] == "pass"
    assert check["live_rows"] == {"core.a": 3, "core.b": 0}
    assert check["list"].startswith("ok")
    assert check == _check_record(root)
    (live_input,) = host.live_inputs
    assert live_input.startswith(b"BEGIN TRANSACTION READ ONLY;")
    (restore,) = [c for _, c in host.calls if "docker run" in " ".join(c)]
    assert "--network none" in restore[2] and "--rm" in restore[2]
    assert "postgres:16" in restore and restore[-1] == entry["backup"]
    assert ["docker", "rm", "-f"] in [c[:3] for _, c in host.calls]
    # The check runs after the dump, before the migration.
    joined = [" ".join(c) for _, c in host.calls]
    first = lambda word: next(i for i, c in enumerate(joined) if word in c)  # noqa: E731
    assert (
        first("pg_dump")
        < first("--list")
        < first("docker run")
        < first("migrate --write")
    )


# ID: 06ee81ab-7d2f-4649-8bc9-5d12f9c0f32c
def test_unreadable_dump_refuses_before_migrating(root: Path) -> None:
    host = _migrating(root)
    host.list_rc = 1
    assert _deploy(root, host, "--migrate") == 1
    assert not _migrate_ran(host)
    assert "start" in host.systemctl_verbs()
    assert _current(root) == OLD
    assert _check_record(root)["verdict"] == "fail"
    assert not any("docker run" in " ".join(c) for _, c in host.calls)


# ID: 0acda82e-46da-466e-9edf-ccdba36a227c
def test_row_count_mismatch_refuses_and_names_the_tables(root: Path) -> None:
    host = _migrating(root)
    host.restored_rows = {"core.a": 2, "core.b": 0}
    assert _deploy(root, host, "--migrate") == 1
    assert not _migrate_ran(host)
    assert "start" in host.systemctl_verbs()
    record = _check_record(root)
    assert record["verdict"] == "fail"
    assert record["differ"] == {"core.a": {"live": 3, "restored": 2}}


# ID: 3a8a49ce-397a-42bb-830b-3c570f012d73
def test_failed_restore_refuses_and_removes_the_container(root: Path) -> None:
    host = _migrating(root)
    host.restore_rc = 1
    assert _deploy(root, host, "--migrate") == 1
    assert not _migrate_ran(host)
    assert ["docker", "rm", "-f"] in [c[:3] for _, c in host.calls]
    assert _check_record(root)["reason"].startswith("restore failed")


# ID: 885744b1-1a2d-43d5-8a3e-6c1507c47c82
def test_without_restore_config_the_dump_is_listed_and_the_deploy_warns(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = _migrating(root, "BACKUP_COMMAND=pg_dump x > {out}\n")
    assert _deploy(root, host, "--migrate") == 0
    assert "WARNING: no restore check" in capsys.readouterr().out
    entry = json.loads((root / "deploy-ledger.jsonl").read_text().splitlines()[-1])
    assert entry["backup_check"]["verdict"] == "unchecked"
    assert any(c[:2] == ["pg_restore", "--list"] for _, c in host.calls)


# ID: bac89eb9-67d1-4315-9afd-15aacce23783
def test_row_counts_parse_only_table_lines() -> None:
    out = b"core.a|3\ncore.weird|name|7\nNOTICE: x\n\npublic.b|0\n"
    assert cd.parse_row_counts(out) == {
        "core.a": 3,
        "core.weird|name": 7,
        "public.b": 0,
    }


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


# -- the approved promotion (ADR-171) ------------------------------------------


def test_the_ledger_records_the_promotion(root: Path) -> None:
    _with_previous(root)
    assert _deploy(root, FakeHost(root)) == 0
    assert _ledger(root)["promotion"] == PROMOTION


def test_a_deploy_without_a_promotion_is_refused_before_building(root: Path) -> None:
    host = FakeHost(root)
    sbin = root / "sbin"
    sbin.mkdir()
    argv = [SHA, "--root", str(root), "--sbin", str(sbin)]
    argv += ["--dev-repo", str(root / "none"), "--law-venv", str(root / "lv")]
    assert cd.main(argv, host=host) == cd.EX_REFUSED
    assert not (root / "releases" / SHA).exists()
    assert not host.commands("tar")


def _refused(root: Path, host: FakeHost, capsys) -> str:
    assert _deploy(root, host) == cd.EX_REFUSED
    assert not (root / "releases" / SHA).exists()
    assert not [c for c in host.calls if c[1][:1] == ["tar"]]
    return capsys.readouterr().err


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"state": "closed", "merged": False}, "closed without being merged"),
        ({"base": {"ref": "main"}}, "does not go into live"),
        ({"head": {"ref": "feature", "sha": SHA}}, "not promote/"),
        ({"head": {"ref": "promote/x", "sha": OLD}}, "its head is"),
    ],
    ids=["closed", "other-base", "not-a-promote-branch", "other-head"],
)
def test_a_promotion_that_is_not_this_commit_is_refused(
    root: Path, capsys, change: dict, reason: str
) -> None:
    host = FakeHost(root)
    host.promotion = {**host.promotion, **change}
    assert reason in _refused(root, host, capsys)


@pytest.mark.parametrize(
    "reviews",
    [
        [],
        [{"user": {"login": "core-claude-bot"}, "state": "APPROVED", "commit_id": SHA}],
        [{"user": {"login": GOVERNOR}, "state": "APPROVED", "commit_id": OLD}],
        [
            {"user": {"login": GOVERNOR}, "state": "APPROVED", "commit_id": SHA},
            {"user": {"login": GOVERNOR}, "state": "DISMISSED", "commit_id": SHA},
        ],
    ],
    ids=["none", "other-account", "older-commit", "dismissed"],
)
def test_only_the_governors_standing_approval_of_this_commit_deploys(
    root: Path, capsys, reviews: list
) -> None:
    host = FakeHost(root)
    host.reviews = reviews
    assert "has not approved" in _refused(root, host, capsys)


def test_a_merged_promotion_can_be_deployed_again_on_a_rebuild(root: Path) -> None:
    host = FakeHost(root)
    host.promotion = {**host.promotion, "state": "closed", "merged": True}
    assert _deploy(root, host) == 0


def test_the_approval_is_read_again_right_before_anything_live_changes(
    root: Path,
) -> None:
    _with_previous(root)
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    assert host.review_reads == 2  # before the build, and after it
    law_before = [c for c in host.calls if "apply-merge" in c[1]]
    assert law_before == []  # nothing changed live before the second read


def test_an_approval_dismissed_during_the_build_stops_the_deploy(
    root: Path, capsys
) -> None:
    _with_previous(root)
    host = FakeHost(root)
    host.law_diff = b"M\0.specs/DECISIONS.md\0"
    host.reviews_later = [
        *host.reviews,
        {"user": {"login": GOVERNOR}, "state": "DISMISSED", "commit_id": SHA},
    ]
    assert _deploy(root, host) == cd.EX_REFUSED
    assert "has not approved" in capsys.readouterr().err
    assert _current(root) == OLD
    assert not (root / "releases" / SHA).exists()
    assert host.law_runs == [] and "restart" not in host.systemctl_verbs()


def test_no_governor_named_is_refused(root: Path, capsys) -> None:
    (root / "pipeline.conf").write_text("GITHUB_REPO=x/y\n")
    assert "GOVERNOR_GITHUB missing" in _refused(root, FakeHost(root), capsys)


def test_the_live_branch_and_governor_can_come_from_deploy_conf(root: Path) -> None:
    (root / "pipeline.conf").write_text("")
    (root / "etc" / "deploy.conf").write_text(
        f"GOVERNOR_GITHUB={GOVERNOR}\nLIVE_BRANCH=prod\n"
    )
    host = FakeHost(root)
    host.promotion["base"] = {"ref": "prod"}
    assert _deploy(root, host) == 0


def test_the_tested_as_option_is_gone(root: Path) -> None:
    with pytest.raises(SystemExit):
        _deploy(root, FakeHost(root), "--tested-as", "e" * 40)


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
def test_claude_md_is_governed_text_delivered_by_core_law() -> None:
    """Law 0040 / #1186: CLAUDE.md reaches the dev tree through law apply-merge
    (a ledger line), never a root copy."""
    assert "CLAUDE.md" in cd.GOVERNED_PATHSPECS
    assert not hasattr(cd.Deployer, "update_claude_md")


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


def _law_venv(root: Path, wheel_sha256: str) -> None:
    law = root / "law-venv"
    law.mkdir()
    (law / "core-release.json").write_text(
        json.dumps({"sha": OLD, "wheel_sha256": wheel_sha256})
    )


class SameWheelHost(FakeHost):
    """Builds the wheel core-law's venv already holds (a merge that left
    src/ alone)."""

    def __init__(self, root: Path, wheel: Path) -> None:
        super().__init__(root)
        self.wheel = wheel

    def run(self, cmd, *, user=None, input=None, check=True):
        result = super().run(cmd, user=user, input=input, check=check)
        if "wheel" in cmd and "--wheel-dir" in cmd:
            target = Path(cmd[cmd.index("--wheel-dir") + 1])
            (target / self.wheel.name).write_bytes(self.wheel.read_bytes())
        return result


def test_a_changed_wheel_runs_core_law_setup_after_the_switch(root: Path) -> None:
    # 2026-10-18: core-law's venv stayed on 65d3eb49 while 1316c543 was live;
    # it was refreshed only by merges that changed infra/core-law-setup.
    _with_previous(root)
    _law_venv(root, "0" * 64)
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    assert host.setup_runs == [["core-law-setup", "--governor", "darek", "--apply"]]
    law_setup = _index(host, lambda c: c[0].endswith("sbin/core-law-setup"))
    restart = _index(host, lambda c: c[0] == "systemctl" and c[4] == "restart")
    assert restart < law_setup
    assert _ledger(root)["law_setup"] == "applied"


def test_the_same_wheel_skips_core_law_setup(root: Path, tmp_path: Path) -> None:
    _with_previous(root)
    wheel = tmp_path / "core_runtime-2.13.0-py3-none-any.whl"
    _wheel(wheel, GOOD_WHEEL)
    _law_venv(root, hashlib.sha256(wheel.read_bytes()).hexdigest())
    host = SameWheelHost(root, wheel)
    assert _deploy(root, host) == 0
    assert host.setup_runs == []
    assert _ledger(root)["law_setup"] is None


def test_an_unreadable_core_law_record_runs_core_law_setup(root: Path) -> None:
    _with_previous(root)
    (root / "law-venv").mkdir()
    (root / "law-venv" / "core-release.json").write_text("not json")
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    assert host.setup_runs == [["core-law-setup", "--governor", "darek", "--apply"]]


def test_a_failed_core_law_setup_for_a_new_wheel_does_not_undo_the_deploy(
    root: Path,
) -> None:
    _with_previous(root)
    _law_venv(root, "0" * 64)
    host = FakeHost(root)
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


def test_leftover_files_identical_to_the_target_do_not_block_the_move(
    root: Path, tmp_path: Path
) -> None:
    # #1246: an untracked copy of a file B adds, byte for byte, blocked
    # every move from 2026-10-18 ("untracked working tree files would be
    # overwritten").
    dev, _a, b = _dev_checkout(tmp_path)
    (dev / ".intent" / "rule.yaml").write_text("v: 2\n")  # core-law applied it
    (dev / "src" / "b.py").write_text("b = 1\n")  # untracked, identical to B
    assert _follower(root, dev).follow_dev_checkout(b).startswith("moved")
    assert _git(dev, "rev-parse", "HEAD") == b
    assert _git(dev, "status", "--porcelain") == ""


def _three_commits(tmp_path: Path) -> tuple[Path, str, str, str]:
    """A dev checkout at A; B and C each change src/a.py and .intent/rule.yaml."""
    dev, a, b = _dev_checkout(tmp_path)
    _git(dev, "reset", "-q", "--hard", b)
    (dev / "src" / "a.py").write_text("a = 3\n")
    (dev / ".intent" / "rule.yaml").write_text("v: 3\n")
    _git(dev, "commit", "-q", "-am", "C")
    c = _git(dev, "rev-parse", "HEAD")
    _git(dev, "reset", "-q", "--hard", a)
    return dev, a, b, c


def test_a_leftover_at_an_older_main_version_is_superseded_not_local_work(
    root: Path, tmp_path: Path
) -> None:
    dev, _a, _b, c = _three_commits(tmp_path)
    (dev / ".intent" / "rule.yaml").write_text("v: 3\n")  # core-law applied C
    (dev / "src" / "a.py").write_text("a = 2\n")  # B's version: in history
    assert _follower(root, dev).follow_dev_checkout(c).startswith("moved")
    assert _git(dev, "rev-parse", "HEAD") == c
    assert (dev / "src" / "a.py").read_text() == "a = 3\n"
    assert _git(dev, "status", "--porcelain") == ""


def test_governed_text_at_an_older_main_version_still_waits_for_core_law(
    root: Path, tmp_path: Path
) -> None:
    dev, a, _b, c = _three_commits(tmp_path)
    (dev / ".intent" / "rule.yaml").write_text("v: 2\n")  # B's law, not C's
    assert _follower(root, dev).follow_dev_checkout(c) == (
        "not moved: governed text differs"
    )
    assert _git(dev, "rev-parse", "HEAD") == a
    assert (dev / ".intent" / "rule.yaml").read_text() == "v: 2\n"


def test_without_a_dev_checkout_nothing_is_done(root: Path) -> None:
    assert _deployer(root, root / "absent").follow_dev_checkout(SHA) is None


# -- step 8b: prune ---------------------------------------------------------


def _release(root: Path, n: int, age_hours: int) -> str:
    """An installed release built *age_hours* ago; returns its sha."""
    sha = f"{n:x}" * 40 if n < 16 else hashlib.sha1(str(n).encode()).hexdigest()
    stamp = root / "releases" / sha / "venv" / "core-release.json"
    stamp.parent.mkdir(parents=True)
    stamp.write_text(json.dumps({"sha": sha}) + "\n")
    built = T0.timestamp() - age_hours * 3600
    os.utime(stamp, (built, built))
    return sha


def _releases(root: Path) -> set[str]:
    return {p.name for p in (root / "releases").iterdir()}


def _old_releases(root: Path) -> list[str]:
    """Current OLD (the oldest build) and five more, newest first."""
    _with_previous(root)
    os.utime(root / "releases" / OLD, (0, 0))
    return [_release(root, n, age) for n, age in zip(range(1, 6), (1, 2, 3, 4, 5))]


def test_a_deploy_prunes_all_but_current_previous_and_the_three_newest(
    root: Path,
) -> None:
    others = _old_releases(root)
    host = FakeHost(root)
    assert _deploy(root, host) == 0
    # The new release is the newest build, so two more of the newest stay.
    assert _releases(root) == {SHA, OLD, *others[:2]}
    assert sorted(_ledger(root)["pruned"]) == sorted(others[2:])


def test_prune_keeps_the_release_core_law_runs(root: Path) -> None:
    others = _old_releases(root)
    law = root / "law-venv"
    law.mkdir()
    (law / "core-release.json").write_text(json.dumps({"sha": others[4]}))
    assert _deploy(root, FakeHost(root)) == 0
    assert _releases(root) == {SHA, OLD, *others[:2], others[4]}


@pytest.mark.parametrize("where", ["maps", "cmdline"])
def test_prune_keeps_a_release_a_running_process_uses(root: Path, where: str) -> None:
    others = _old_releases(root)
    host = FakeHost(root)
    path = f"{root}/releases/{others[3]}/venv"
    host.procs = [
        f"7f00-7f01 r-xp 0 08:01 42 {path}/lib/python3.12/site-packages/x.so\n"
        if where == "maps"
        else f"{path}/bin/python -I -m cli.admin_cli daemon start"
    ]
    assert _deploy(root, host) == 0
    assert _releases(root) == {SHA, OLD, *others[:2], others[3]}


def test_prune_never_touches_symlinks_or_other_names(
    root: Path, tmp_path: Path
) -> None:
    _old_releases(root)
    outside = tmp_path / "outside"
    (outside / "venv").mkdir(parents=True)
    linked = "c" * 40
    (root / "releases" / linked).symlink_to(outside)
    (root / "releases" / "scratch").mkdir()
    (root / "releases" / ("d" * 39)).mkdir()
    assert _deploy(root, FakeHost(root)) == 0
    assert {linked, "scratch", "d" * 39} <= _releases(root)
    assert (outside / "venv").is_dir()


def test_a_prune_error_is_logged_and_never_fails_the_deploy(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    others = _old_releases(root)
    host = FakeHost(root)
    host.procs_error = PermissionError("/proc/1/maps")
    assert _deploy(root, host) == 0
    assert _current(root) == SHA
    # Processes unknown: nothing is deleted.
    assert _releases(root) == {SHA, OLD, *others}
    assert _ledger(root)["pruned"].startswith("failed: ")
    assert "old releases not pruned" in capsys.readouterr().out


def test_an_unreadable_core_law_record_prunes_nothing(root: Path) -> None:
    others = _old_releases(root)
    law = root / "law-venv"
    law.mkdir()
    (law / "core-release.json").write_text("not json")
    assert _deploy(root, FakeHost(root)) == 0
    assert _releases(root) == {SHA, OLD, *others}


def test_a_switched_back_deploy_prunes_nothing(root: Path) -> None:
    others = _old_releases(root)
    host = FakeHost(root)
    host.inactive = {"core-api.service"}
    assert _deploy(root, host) == cd.EX_REFUSED
    assert _releases(root) == {OLD, *others}
