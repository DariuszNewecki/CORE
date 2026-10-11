"""core-law-setup (ADR-170 Stage 1): the governor's root act that creates the custodian.

The real script runs against a temporary layout with a scripted Host:
accounts, ownership, processes and HTTP are simulated and recorded, so these
tests prove the procedure -- what runs as which account, what is refused,
what a plan-only run leaves alone, what a re-run keeps -- without root.
Modes are real (chmod on the temporary tree). The real ownership, sudo's
password prompt and the denials are proven when the governor runs it: its
own probes (step 8) and ADR-170 acceptance checks 3-9.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "infra" / "core-law-setup"
VERSION = "2.14.0"
WHEEL_SHA = "4" * 64


def _load(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve the module by name
    loader.exec_module(module)
    return module


cls = _load("core_law_setup", SCRIPT)

LOCK = b"""
[[package]]
name = "pyyaml"
version = "6.0.2"
groups = ["main"]
files = [{file = "PyYAML-6.0.2-cp312-cp312-manylinux.whl", hash = "sha256:aaa"}]
"""


def _pypi(version: str = VERSION, wheels: int = 1) -> bytes:
    urls = [
        {
            "packagetype": "bdist_wheel",
            "filename": f"core_runtime-{version}-py3-none-any.whl",
            "digests": {"sha256": WHEEL_SHA},
        }
    ] * wheels + [
        {"packagetype": "sdist", "filename": "x.tar.gz", "digests": {"sha256": "0"}}
    ]
    return json.dumps({"info": {"version": version}, "urls": urls}).encode()


class FakeHost(cls.Host):
    def __init__(self) -> None:
        self.root = True
        self.accounts = {
            name: SimpleNamespace(pw_shell="/bin/bash", pw_dir=f"/home/{name}")
            for name in ("darek", "core-claude", "core", "core-darek")
        }
        self.owners: dict[Path, tuple[str, str]] = {}
        self.calls: list[tuple[list[str], str | None]] = []
        self.fetched: list[str] = []
        self.install_version = VERSION
        self.inject_pth = False
        self.allowed_probes: set[tuple[str, str]] = set()
        self.groups = {"core-darek": ["core-darek", "core-dev", "docker", "sudo"]}

    def groups_of(self, user: str) -> list[str]:
        return self.groups.get(user, [user, "core-dev"])

    def is_root(self) -> bool:
        return self.root

    def account(self, name: str):  # type: ignore[override]
        return self.accounts.get(name)

    def fetch(self, url: str, timeout: float = 30.0) -> bytes:
        self.fetched.append(url)
        return _pypi() if url.startswith(cls.PYPI) else LOCK

    def owner(self, path: Path) -> tuple[str, str]:
        return self.owners.get(path, ("core", "core-dev"))

    def chown(self, path: Path, user: str, group: str) -> None:
        self.owners[path] = (user, group)

    def run(self, cmd, *, user=None, cwd=None, input=None, check=True):  # type: ignore[override]
        self.calls.append((list(cmd), user))
        out, code = b"", 0
        if cmd[0] == "useradd":
            self.accounts["core-law"] = SimpleNamespace(
                pw_shell="/usr/sbin/nologin", pw_dir=cmd[cmd.index("--home-dir") + 1]
            )
        elif cmd[0] == "ssh-keygen" and "-t" in cmd:
            key = Path(cmd[cmd.index("-f") + 1])
            key.write_text("PRIVATE\n")
            key.with_suffix(".pub").write_text("ssh-ed25519 AAAA core-law-ledger\n")
        elif cmd[0] == "ssh-keygen" and "-y" in cmd:
            out = b"ssh-ed25519 AAAA core-law-ledger\n"
        elif cmd[:4] == ["/usr/bin/python3", "-I", "-m", "venv"]:
            venv = Path(cmd[4])
            (venv / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
            (venv / "bin").mkdir()
            (venv / "bin" / "core-admin").write_text("#!/bin/sh\n")
        elif "pip" in cmd and str(cmd[-1]).endswith("core-runtime.txt"):
            sp = Path(cmd[0]).parents[1] / "lib" / "python3.12" / "site-packages"
            meta = sp / f"core_runtime-{self.install_version}.dist-info"
            meta.mkdir()
            (meta / "METADATA").write_text(
                f"Name: core-runtime\nVersion: {self.install_version}\n"
            )
            if self.inject_pth:
                (sp / "dev.pth").write_text("/opt/dev/CORE/src\n")
        elif cmd[0] == "mv" and user is not None:
            code = 0 if (user, "mv-repo") in self.allowed_probes else 1
        elif cmd[:2] == ["sh", "-c"] and user is not None:
            code = (
                0 if (user, cmd[2]) in self.allowed_probes or "README" in cmd[2] else 1
            )
        result = subprocess.CompletedProcess(cmd, code, out, b"")
        if check and code:
            raise cls.Refused(f"failed: {cmd}")
        return result


@pytest.fixture
def world(tmp_path: Path) -> tuple[FakeHost, object]:
    repo = tmp_path / "dev" / "CORE"
    (repo / ".intent" / "rules").mkdir(parents=True)
    (repo / ".intent" / "rules" / "a.json").write_text("{}\n")
    (repo / ".specs" / "decisions").mkdir(parents=True)
    (repo / ".specs" / "decisions" / "ADR-1.md").write_text("# ADR-1\n")
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / ".claude" / "hooks" / "h.sh").write_text("#!/bin/sh\n")
    (repo / ".claude" / "settings.json").write_text("{}\n")
    (repo / ".claude" / "settings.local.json").write_text("{}\n")
    (repo / "CLAUDE.md").write_text("contract\n")
    (repo / "README.md").write_text("readme\n")
    (repo / ".env").write_text("SECRET=1\n")
    (repo / ".env.local").write_text("SECRET=2\n")
    (repo / ".env.production").write_text("SECRET=3\n")
    (repo / ".env.example").write_text("DATABASE_URL=\n")
    (repo / ".env.test").write_text("DATABASE_URL=postgresql://test\n")
    (repo / ".secrets").mkdir()
    (repo / ".secrets" / "core.env").write_text("CORE_MASTER_KEY=x\n")
    (repo / "src").mkdir()
    for path in (repo, repo / ".intent", repo / ".specs"):
        path.chmod(0o2775)
    layout = cls.Layout(
        law_home=tmp_path / "opt" / "core-law",
        repo=repo,
        core_root=tmp_path / "opt" / "core",
        sudoers=tmp_path / "etc" / "sudoers.d" / "core-law",
        ancestors_stop=tmp_path,
    )
    layout.sudoers.parent.mkdir(parents=True)
    return FakeHost(), layout


def _main(world, *extra: str) -> int:
    host, layout = world
    return cls.main(
        ["--version", VERSION, "--governor", "darek", *extra], host=host, layout=layout
    )


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_plan_only_changes_nothing(world) -> None:
    host, layout = world
    assert _main(world) == 0
    assert not layout.law_home.exists() and not layout.sudoers.exists()
    assert host.owners == {}
    assert all(cmd[0] not in ("useradd", "ssh-keygen") for cmd, _ in host.calls)
    # It still checks the release exists, over HTTPS, without git.
    assert host.fetched == [
        f"{cls.PYPI}/{VERSION}/json",
        f"{cls.GITHUB_RAW}/v{VERSION}/poetry.lock",
    ]


def test_apply_creates_the_custodian(world) -> None:
    host, layout = world
    assert _main(world, "--apply") == 0

    assert host.accounts["core-law"].pw_shell == "/usr/sbin/nologin"
    keygen = [(c, u) for c, u in host.calls if c[0] == "ssh-keygen"]
    assert keygen and keygen[0][1] == "core-law"
    assert layout.key.read_text() == "PRIVATE\n" and _mode(layout.key) == 0o600
    assert host.owners[layout.key] == ("core-law", "core-law")
    assert not layout.key.is_relative_to(layout.repo)

    # Released code only: hash-pinned binary wheels, then verified and swapped.
    pins = [c for c, _ in host.calls if "pip" in c]
    assert all("--require-hashes" in c and "--only-binary=:all:" in c for c in pins)
    assert (layout.build / "core-runtime.txt").read_text() == (
        f"core-runtime=={VERSION} --hash=sha256:{WHEEL_SHA}\n"
    )
    assert cls.installed_version(layout.venv) == VERSION
    assert host.owners.get(layout.venv) is None  # root's, never core-law's
    assert not any(c[0] == "git" for c, _ in host.calls)

    for rel in (
        ".intent/rules/a.json",
        ".specs/decisions/ADR-1.md",
        "CLAUDE.md",
        ".claude/settings.json",
        ".claude/hooks/h.sh",
    ):
        assert host.owners[layout.repo / rel] == ("core-law", "core-law")
        assert _mode(layout.repo / rel) == 0o644
    assert _mode(layout.repo / ".intent") == 0o755  # setgid and group-write gone
    assert host.owners[layout.repo] == ("root", "core-dev")
    assert _mode(layout.repo) == 0o3775
    assert host.owners[layout.repo / ".claude"] == ("core-law", "core-dev")
    assert _mode(layout.repo / ".claude") == 0o3775
    assert (layout.repo / ".claude" / "settings.local.json") not in host.owners
    assert host.owners[layout.repo / "README.md"] == ("core-claude", "core-dev")
    # Committed, non-secret templates are handed over by name ...
    for name in (".env.example", ".env.test"):
        assert host.owners[layout.repo / name] == ("core-claude", "core-dev")
    # ... every other .env* file and .secrets stay with their owner.
    for name in (
        ".env",
        ".env.local",
        ".env.production",
        ".secrets",
        ".secrets/core.env",
    ):
        assert (layout.repo / name) not in host.owners

    law = layout.law_root
    assert (law / ".intent" / "rules" / "a.json").read_text() == "{}\n"
    assert host.owners[law / ".intent"] == ("core-law", "core-law")
    assert host.owners[law] == ("root", "root")

    sudoers = layout.sudoers.read_text()
    assert "NOPASSWD" not in sudoers
    assert f"darek ALL=(core-law) {layout.venv}/bin/core-admin law apply *" in sudoers
    assert _mode(layout.sudoers) == 0o440
    assert any(c[0] == "visudo" for c, _ in host.calls)

    probes = [(c[2], u) for c, u in host.calls if c[:2] == ["sh", "-c"] and u]
    assert {u for _, u in probes} == {"core-claude", "core", "core-darek"}


def test_rerun_keeps_the_key_and_the_venv(world) -> None:
    host, layout = world
    assert _main(world, "--apply") == 0
    layout.key.write_text("PRIVATE-FROM-FIRST-RUN\n")
    host.calls.clear()
    host.fetched.clear()
    assert _main(world, "--apply") == 0
    assert layout.key.read_text() == "PRIVATE-FROM-FIRST-RUN\n"
    assert not any(c[0] in ("useradd", "ssh-keygen") for c, _ in host.calls)
    assert not any("venv" in c for c, _ in host.calls)
    assert host.fetched == []


def test_a_lost_public_key_is_rederived_not_regenerated(world) -> None:
    _host, layout = world
    assert _main(world, "--apply") == 0
    layout.key.with_suffix(".pub").unlink()
    assert _main(world, "--apply") == 0
    assert layout.key.read_text() == "PRIVATE\n"
    assert layout.key.with_suffix(".pub").exists()


@pytest.mark.parametrize(
    "governor", ["core-darek", "core-claude", "root", "nosuchuser"]
)
def test_refuses_a_governor_that_is_not_human(world, governor: str) -> None:
    host, layout = world
    code = cls.main(
        ["--version", VERSION, "--governor", governor, "--apply"],
        host=host,
        layout=layout,
    )
    assert code == 1 and not layout.law_home.exists()


def test_refuses_without_root_or_with_a_bad_version_or_foreign_account(world) -> None:
    host, layout = world
    host.root = False
    assert _main(world, "--apply") == 1
    host.root = True
    assert (
        cls.main(["--version", "main", "--governor", "darek"], host=host, layout=layout)
        == 1
    )
    host.accounts["core-law"] = SimpleNamespace(
        pw_shell="/bin/bash", pw_dir="/home/core-law"
    )
    assert _main(world, "--apply") == 1
    assert not layout.law_home.exists()


def test_a_venv_that_reaches_outside_itself_is_refused_and_not_swapped(world) -> None:
    host, layout = world
    host.inject_pth = True
    assert _main(world, "--apply") == 1
    assert not layout.venv.exists()
    host.inject_pth = False
    host.install_version = "2.13.0"
    assert _main(world, "--apply") == 1


def test_symlink_in_governed_text_is_refused(world) -> None:
    _host, layout = world
    (layout.repo / ".specs" / "evil").symlink_to("/etc")
    assert _main(world, "--apply") == 1


def test_a_probe_that_succeeds_fails_the_run_and_is_undone(world) -> None:
    host, _layout = world
    host.allowed_probes.add(("core-claude", "mv .intent .intent-custody-probe"))
    assert _main(world, "--apply") == 1
    undo = [c for c, u in host.calls if u is None and c[:2] == ["sh", "-c"]]
    assert undo.count(["sh", "-c", cls.PROBE_UNDO]) == 3 * len(cls.PROBES)


def test_release_law_that_differs_is_reported(world) -> None:
    _host, layout = world
    assert _main(world, "--apply") == 0
    (layout.law_root / ".intent" / "rules" / "a.json").write_text('{"drift": 1}\n')
    assert _main(world, "--apply") == 1


def test_release_wheel_needs_exactly_one_wheel_of_that_version() -> None:
    assert cls.release_wheel(_pypi(), VERSION)[1] == WHEEL_SHA
    with pytest.raises(cls.Refused):
        cls.release_wheel(_pypi("2.13.0"), VERSION)
    with pytest.raises(cls.Refused):
        cls.release_wheel(_pypi(wheels=2), VERSION)


def test_lock_pinning_is_core_deploys_for_the_runtime_group_only() -> None:
    deploy = _load("core_deploy_parity", REPO / "infra" / "core-deploy")
    lock_bytes = (REPO / "poetry.lock").read_bytes()
    lock = __import__("tomllib").loads(lock_bytes.decode())

    def entries(text: str) -> dict[str, str]:
        found = {}
        for entry in re.split(r"\n(?=\S)", text.strip()):
            found[entry.split("==", 1)[0]] = entry
        return found

    ours, theirs = (
        entries(cls.requirements_from_lock(lock_bytes)),
        entries(deploy.requirements_from_lock(lock_bytes)),
    )
    runtime = {
        p["name"] for p in lock["package"] if "main" in p.get("groups", ["main"])
    }
    assert set(ours) == runtime
    assert all(ours[name] == theirs[name] for name in ours)  # same pins, same hashes
    assert "coverage" not in ours and "sphinxcontrib-jsmath" not in ours


def test_dev_only_packages_are_left_out_and_ungrouped_ones_kept() -> None:
    lock = b"""
[[package]]
name = "runtime-only"
version = "1"
groups = ["main"]
files = [{file = "a.whl", hash = "sha256:aaa"}]

[[package]]
name = "both"
version = "1"
groups = ["dev", "main"]
files = [{file = "b.whl", hash = "sha256:bbb"}]

[[package]]
name = "dev-only"
version = "1"
groups = ["dev"]
files = [{file = "c.whl", hash = "sha256:ccc"}]

[[package]]
name = "no-groups"
version = "1"
files = [{file = "d.whl", hash = "sha256:ddd"}]
"""
    text = cls.requirements_from_lock(lock)
    assert "runtime-only==1" in text and "both==1" in text and "no-groups==1" in text
    assert "dev-only" not in text


def test_plan_shows_owner_and_mode_now_and_after(world, capsys) -> None:
    _host, layout = world
    assert _main(world) == 0
    out = capsys.readouterr().out
    row = next(
        line for line in out.splitlines() if line.strip().startswith(f"{layout.repo} ")
    )
    assert "core:core-dev 2775" in row and "-> root:core-dev 3775 (sticky)" in row
    parent = next(
        line
        for line in out.splitlines()
        if line.strip().startswith(f"{layout.repo.parent} ")
    )
    assert "-> root:root 755" in parent


def test_the_repositorys_parent_is_taken_from_core(world) -> None:
    host, layout = world
    assert _main(world, "--apply") == 0
    assert host.owners[layout.repo.parent] == ("root", "root")
    assert _mode(layout.repo.parent) == 0o755


def test_root_equivalent_groups_are_named_not_hidden(world, capsys) -> None:
    _host, _layout = world
    assert _main(world) == 0
    out = capsys.readouterr().out
    assert "NOT PROTECTED from core-darek: member of docker, sudo" in out
    assert "root without any password" in out
    assert "core-claude: none" in out
    summary = out.split("The sticky bit and ownership do not hold against:", 1)[1]
    assert "core-darek" in summary


def test_a_repository_rename_that_succeeds_fails_the_run_and_is_undone(world) -> None:
    host, layout = world
    host.allowed_probes.add(("core", "mv-repo"))
    assert _main(world, "--apply") == 1
    undo = [
        c
        for c, u in host.calls
        if u is None
        and c[:2] == ["sh", "-c"]
        and "custody-probe" in c[2]
        and str(layout.repo) in c[2]
    ]
    assert undo
