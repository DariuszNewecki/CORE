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

import hashlib
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
RELEASE = "a" * 40
WHEEL = b"the wheel core-deploy built"
WHEEL_NAME = "core_runtime-2.14.2-py3-none-any.whl"
WHEEL_SHA = hashlib.sha256(WHEEL).hexdigest()
RECORD = json.dumps({"sha": RELEASE, "wheel_sha256": WHEEL_SHA}).encode() + b"\n"


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


class FakeHost(cls.Host):
    def __init__(self) -> None:
        self.root = True
        self.accounts = {
            name: SimpleNamespace(pw_shell="/bin/bash", pw_dir=f"/home/{name}")
            for name in ("darek", "core-claude", "core", "core-darek")
        }
        self.owners: dict[Path, tuple[str, str]] = {}
        self.calls: list[tuple[list[str], str | None]] = []
        # The sha256 pip records for the core-runtime file it installs.
        self.install_sha = WHEEL_SHA
        self.inject_pth = False
        self.allowed_probes: set[tuple[str, str]] = set()
        self.groups = {
            "core": ["core", "core-dev", "docker", "sudo"],
            "darek": ["darek", "sudo"],
        }

    def groups_of(self, user: str) -> list[str]:
        return self.groups.get(user, [user, "core-dev"])

    def is_root(self) -> bool:
        return self.root

    def account(self, name: str):  # type: ignore[override]
        return self.accounts.get(name)

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
            meta = sp / "core_runtime-2.14.2.dist-info"
            meta.mkdir()
            (meta / "METADATA").write_text("Name: core-runtime\nVersion: 2.14.2\n")
            (meta / "direct_url.json").write_text(
                json.dumps(
                    {
                        "archive_info": {"hashes": {"sha256": self.install_sha}},
                        "url": f"file://{Path(cmd[-1]).parent / WHEEL_NAME}",
                    }
                )
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
        system_units=tmp_path / "etc" / "systemd" / "system",
        ancestors_stop=tmp_path,
        private_names_seed=tmp_path / "home" / "core-claude" / "private-names.conf",
    )
    layout.sudoers.parent.mkdir(parents=True)
    layout.system_units.mkdir(parents=True)
    _release(layout)
    return FakeHost(), layout


def _release(layout, sha: str = RELEASE, wheel: bytes = WHEEL) -> Path:
    """A release as core-deploy leaves it, made live."""
    release = layout.releases / sha
    (release / "venv").mkdir(parents=True)
    (release / "venv" / "core-release.json").write_bytes(
        json.dumps({"sha": sha, "wheel_sha256": WHEEL_SHA}).encode() + b"\n"
    )
    (release / "dist").mkdir()
    (release / "dist" / WHEEL_NAME).write_bytes(wheel)
    (release / "dist" / "poetry.lock").write_bytes(LOCK)
    if layout.current.is_symlink():
        layout.current.unlink()
    layout.current.symlink_to(Path("releases") / sha)
    return release


def _main(world, *extra: str) -> int:
    host, layout = world
    return cls.main(["--governor", "core-darek", *extra], host=host, layout=layout)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_plan_only_changes_nothing(world) -> None:
    host, layout = world
    assert _main(world) == 0
    assert not layout.law_home.exists()
    assert host.owners == {}
    assert all(cmd[0] not in ("useradd", "ssh-keygen") for cmd, _ in host.calls)
    # It still checks the live release's wheel, and installs nothing.
    assert not any("pip" in cmd for cmd, _ in host.calls)


def test_apply_creates_the_custodian(world) -> None:
    host, layout = world
    assert _main(world, "--apply") == 0

    assert host.accounts["core-law"].pw_shell == "/usr/sbin/nologin"
    keygen = [(c, u) for c, u in host.calls if c[0] == "ssh-keygen"]
    assert keygen and keygen[0][1] == "core-law"
    assert layout.key.read_text() == "PRIVATE\n" and _mode(layout.key) == 0o600
    assert host.owners[layout.key] == ("core-law", "core-law")
    assert not layout.key.is_relative_to(layout.repo)

    # The live release's wheel only: hash-pinned binary wheels, verified, swapped.
    pins = [c for c, _ in host.calls if "pip" in c]
    assert all("--require-hashes" in c and "--only-binary=:all:" in c for c in pins)
    assert "--no-index" in pins[-1]  # core-runtime never comes from an index
    copy = layout.build / WHEEL_NAME
    assert copy.read_bytes() == WHEEL
    assert (layout.build / "core-runtime.txt").read_text() == (
        f"{copy} --hash=sha256:{WHEEL_SHA}\n"
    )
    assert cls.installed_wheel_sha256(layout.venv) == WHEEL_SHA
    assert (layout.venv / "core-release.json").read_bytes() == RECORD
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

    # The merge is the only approval of law: no sudo rule reaches core-law.
    assert not layout.sudoers.exists()
    assert not any(c[0] == "visudo" for c, _ in host.calls)

    probes = [(c[2], u) for c, u in host.calls if c[:2] == ["sh", "-c"] and u]
    assert {u for _, u in probes} == {"core-claude", "core", "core-darek"}


def test_rerun_keeps_the_key_and_the_venv(world) -> None:
    host, layout = world
    assert _main(world, "--apply") == 0
    layout.key.write_text("PRIVATE-FROM-FIRST-RUN\n")
    host.calls.clear()
    assert _main(world, "--apply") == 0
    assert layout.key.read_text() == "PRIVATE-FROM-FIRST-RUN\n"
    assert not any(c[0] in ("useradd", "ssh-keygen") for c, _ in host.calls)
    assert not any("venv" in c for c, _ in host.calls)


def test_a_lost_public_key_is_rederived_not_regenerated(world) -> None:
    _host, layout = world
    assert _main(world, "--apply") == 0
    layout.key.with_suffix(".pub").unlink()
    assert _main(world, "--apply") == 0
    assert layout.key.read_text() == "PRIVATE\n"
    assert layout.key.with_suffix(".pub").exists()


@pytest.mark.parametrize(
    "governor", ["darek", "core-claude", "core-runner", "root", "nosuchuser"]
)
def test_refuses_a_governor_outside_the_register(world, governor: str) -> None:
    """Another role's account, root, unknown, or a host administrator (rule 6)."""
    host, layout = world
    code = cls.main(
        ["--governor", governor, "--apply"],
        host=host,
        layout=layout,
    )
    assert code == 1 and not layout.law_home.exists()


def test_refuses_without_root_or_with_a_foreign_account(world) -> None:
    host, layout = world
    host.root = False
    assert _main(world, "--apply") == 1
    host.root = True
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
    host.install_sha = "0" * 64  # pip installed some other file
    assert _main(world, "--apply") == 1
    assert not layout.venv.exists()


def test_symlink_in_governed_text_is_refused(world) -> None:
    _host, layout = world
    (layout.repo / ".specs" / "evil").symlink_to("/etc")
    assert _main(world, "--apply") == 1


def test_a_probe_that_succeeds_fails_the_run_and_is_undone(world) -> None:
    host, _layout = world
    host.allowed_probes.add(("core-claude", "mv -f .intent .intent-custody-probe"))
    assert _main(world, "--apply") == 1
    undo = [c for c, u in host.calls if u is None and c[:2] == ["sh", "-c"]]
    assert undo.count(["sh", "-c", cls.PROBE_UNDO]) == 3 * len(cls.PROBES)


def test_release_law_that_differs_is_reported(world) -> None:
    _host, layout = world
    assert _main(world, "--apply") == 0
    (layout.law_root / ".intent" / "rules" / "a.json").write_text('{"drift": 1}\n')
    assert _main(world, "--apply") == 1


def test_only_the_wheel_core_deploy_hashed_for_the_live_release_is_accepted(
    world, capsys
) -> None:
    host, layout = world
    release = cls.live_release(layout)
    assert (release.sha, release.wheel_sha256) == (RELEASE, WHEEL_SHA)

    wheel = layout.releases / RELEASE / "dist" / WHEEL_NAME
    wheel.write_bytes(b"a different wheel")
    assert _main(world) == 1
    assert "not the wheel core-deploy built" in capsys.readouterr().err
    wheel.write_bytes(WHEEL)

    record = layout.releases / RELEASE / "venv" / "core-release.json"
    record.write_text(json.dumps({"sha": "b" * 40, "wheel_sha256": WHEEL_SHA}))
    assert _main(world) == 1
    assert "does not describe release" in capsys.readouterr().err
    record.write_bytes(RECORD)

    # A release deployed before core-deploy kept its wheel.
    old = _release(layout, sha="c" * 40)
    for kept in (old / "dist").iterdir():
        kept.unlink()
    assert _main(world) == 1
    assert "keeps no wheel and lock" in capsys.readouterr().err

    # Something at `current` that is not a link to a release.
    layout.current.unlink()
    layout.current.mkdir()
    assert _main(world) == 1
    assert "nothing is deployed" in capsys.readouterr().err
    assert not any("pip" in cmd for cmd, _ in host.calls)


def test_a_fresh_host_seeds_the_law_before_anything_is_deployed(world, capsys) -> None:
    """#1085: core-law-setup, core-runtime-setup, core-deploy, core-law-setup."""
    host, layout = world
    layout.current.unlink()
    assert _main(world, "--apply") == 0
    out = capsys.readouterr().out
    assert "nothing deployed yet" in out
    assert "After the first core-deploy, run core-law-setup --apply again" in out
    # What core-runtime-setup needs is there ...
    assert (layout.law_root / ".intent" / "rules" / "a.json").read_text() == "{}\n"
    assert host.owners[layout.law_root / ".intent"] == ("core-law", "core-law")
    assert host.accounts["core-law"].pw_shell == "/usr/sbin/nologin"
    # ... and nothing that needs a release: no venv, no timers that would run it.
    assert not layout.venv.exists()
    assert not any("pip" in cmd for cmd, _ in host.calls)
    assert not any(layout.system_units.iterdir())

    # After the first core-deploy, the second run completes the setup.
    layout.current.symlink_to(Path("releases") / RELEASE)
    assert _main(world, "--apply") == 0
    assert "core-law-setup --apply again" not in capsys.readouterr().out
    assert cls.installed_wheel_sha256(layout.venv) == WHEEL_SHA
    assert not any(layout.system_units.iterdir())


def test_a_venv_from_another_wheel_is_replaced_by_the_live_release(world) -> None:
    host, layout = world
    assert _main(world, "--apply") == 0
    # The venv a PyPI install left: no recorded file hash, no release record.
    sp = cls.site_packages(layout.venv)
    (sp / "core_runtime-2.14.2.dist-info" / "direct_url.json").unlink()
    (layout.venv / "core-release.json").unlink()
    host.calls.clear()
    assert _main(world, "--apply") == 0
    assert any("pip" in cmd for cmd, _ in host.calls)
    assert cls.installed_wheel_sha256(layout.venv) == WHEEL_SHA
    assert (layout.venv / "core-release.json").read_bytes() == RECORD


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
    assert "NOT PROTECTED from core: member of docker, sudo" in out
    assert "root without any password" in out
    assert "core-claude: none" in out
    summary = out.split("The sticky bit and ownership do not hold against:", 1)[1]
    assert "NOT PROTECTED from core:" in summary


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


# -- no auto-apply (2026-10-18) -------------------------------------------------

AUTO_UNITS = (
    "core-law-auto-apply.service",
    "core-law-auto-apply.timer",
    "core-law-digest.service",
    "core-law-digest.timer",
)


def test_setup_installs_neither_auto_apply_nor_digest(world) -> None:
    # 2026-10-18: auto-apply applied record-only proposals from var/law-proposals,
    # which every core-dev account can write: .specs/ changed without a merge.
    host, layout = world
    assert _main(world, "--apply") == 0
    for name in AUTO_UNITS:
        assert not (layout.system_units / name).exists()
    assert not [c for c in host.calls if c[0][:2] == ["systemctl", "enable"]]


def test_setup_disables_and_deletes_installed_auto_apply_units(world) -> None:
    host, layout = world
    for name in AUTO_UNITS:
        (layout.system_units / name).write_text("[Unit]\n")
    assert _main(world, "--apply") == 0
    for name in AUTO_UNITS:
        assert not (layout.system_units / name).exists()
    commands = [c[0] for c in host.calls if c[0][0] == "systemctl"]
    # Timers first, so neither fires a service while it is being removed.
    disable = commands.index(["systemctl", "disable", "--now", *cls.REMOVED_UNITS])
    assert cls.REMOVED_UNITS[:2] == (
        "core-law-auto-apply.timer",
        "core-law-digest.timer",
    )
    assert commands.index(["systemctl", "daemon-reload"]) > disable


def test_without_apply_the_units_are_only_named(world, capsys) -> None:
    _host, layout = world
    for name in AUTO_UNITS:
        (layout.system_units / name).write_text("[Unit]\n")
    assert _main(world) == 0
    assert "would: systemctl disable --now core-law-auto-apply.timer" in (
        capsys.readouterr().out
    )
    for name in AUTO_UNITS:
        assert (layout.system_units / name).is_file()


def test_units_are_removed_on_a_fresh_host_too(world) -> None:
    _host, layout = world
    layout.current.unlink()
    (layout.system_units / "core-law-auto-apply.timer").write_text("[Unit]\n")
    assert _main(world, "--apply") == 0
    assert not (layout.system_units / "core-law-auto-apply.timer").exists()


def _private_seed(world, *, owner: str = "core-claude") -> Path:
    """The assistant's own copy of the private-names configuration."""
    host, layout = world
    seed = layout.private_names_seed
    seed.parent.mkdir(parents=True)
    names = seed.parent / "names.txt"
    names.write_text("Osric Pell\n")
    seed.write_text(
        f"GITHUB_REPO=o/tool\nCHECKOUT=/opt/dev/tool\nLIBRARY=/opt/dev/lib\nNAMES={names}\n"
    )
    host.owners[seed] = host.owners[names] = (owner, owner)
    return names


def test_private_names_are_seeded_once_and_owned_by_core_law(world) -> None:
    host, layout = world
    _private_seed(world)
    assert _main(world, "--apply") == 0
    target = layout.private_names
    conf = (target / "private-names.conf").read_text()
    assert f"NAMES={target / 'names.txt'}\n" in conf
    assert "LIBRARY=/opt/dev/lib\n" in conf
    assert (target / "names.txt").read_text() == "Osric Pell\n"
    for path in (target, target / "private-names.conf", target / "names.txt"):
        assert host.owners[path] == ("core-law", "core-law")
    assert _mode(target) == 0o755 and _mode(target / "names.txt") == 0o644
    assert host.owners[layout.law_root] == ("root", "root")
    # Kept on a re-run: a changed seed does not replace core-law's copy.
    layout.private_names_seed.write_text("GITHUB_REPO=o/other\n")
    assert _main(world, "--apply") == 0
    assert "GITHUB_REPO=o/tool\n" in (target / "private-names.conf").read_text()


def test_private_names_plan_only_seeds_nothing(world) -> None:
    _, layout = world
    _private_seed(world)
    assert _main(world) == 0
    assert not layout.private_names.exists()


def test_a_private_names_seed_that_is_not_the_assistants_is_refused(world) -> None:
    host, layout = world
    names = _private_seed(world)
    host.owners[names] = ("root", "root")  # e.g. NAMES=/etc/shadow
    assert _main(world, "--apply") == 1
    assert not (layout.private_names / "private-names.conf").exists()


def test_a_private_names_seed_that_is_a_link_is_refused(world) -> None:
    host, layout = world
    names = _private_seed(world)
    names.unlink()
    names.symlink_to(layout.repo / ".env")
    host.owners[names] = ("core-claude", "core-claude")
    assert _main(world, "--apply") == 1
    assert not (layout.private_names / "private-names.conf").exists()


def test_without_a_seed_nothing_is_made_and_the_run_still_succeeds(
    world, capsys
) -> None:
    _, layout = world
    assert _main(world, "--apply") == 0
    assert not layout.private_names.exists()
    assert "stay refused until there is one" in capsys.readouterr().out
