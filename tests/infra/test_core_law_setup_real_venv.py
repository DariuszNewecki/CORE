"""core-law-setup's venv step with a real venv and a real installed entry point.

test_core_law_setup.py simulates processes; that hid a real defect: the
venv was built at ``venv.new`` and renamed, and a venv records its own path
in its entry points, so the installed ``core-admin`` pointed at a directory
that no longer existed. Here the venv step runs for real -- ``python -m
venv``, ``pip install`` of the live release's hash-checked wheel file, and
the installed ``core-admin`` executed -- and a failing upgrade must put the
previous venv back with its entry point still working. The sudoers text is
checked by the real ``visudo``.

The wheel is a stand-in named core-runtime with a ``core-admin`` console
script, laid out in a release as core-deploy leaves it; no network. The account switch (``runuser -u core-law``) is the only
part not real: the command runs as the test's own account.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(
        "core_law_setup_real", str(REPO / "infra" / "core-law-setup")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


cls = _load()


def _wheel(folder: Path, version: str, body: str) -> tuple[Path, str]:
    """A core-runtime wheel whose core-admin prints *body*."""
    name = f"core_runtime-{version}-py3-none-any.whl"
    dist = f"core_runtime-{version}.dist-info"
    files = {
        "core_admin_standin/__init__.py": f"def app():\n    print({body!r})\n",
        f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: core-runtime\nVersion: {version}\n",
        f"{dist}/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{dist}/entry_points.txt": "[console_scripts]\ncore-admin = core_admin_standin:app\n",
    }
    record = []
    for path, text in files.items():
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(text.encode()).digest()
        ).rstrip(b"=")
        record.append(f"{path},sha256={digest.decode()},{len(text.encode())}")
    record.append(f"{dist}/RECORD,,")
    files[f"{dist}/RECORD"] = "\n".join(record) + "\n"
    path = folder / name
    with zipfile.ZipFile(path, "w") as zf:
        for member, text in files.items():
            zf.writestr(member, text)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


# The stand-in has no runtime dependencies. A dev-only package is listed
# whose wheel exists nowhere: installing it would fail offline, so a passing
# install proves dev packages are never attempted.
LOCK = (
    b'[[package]]\nname = "dev-only-tool"\nversion = "9.9"\ngroups = ["dev"]\n'
    b'files = [{file = "dev_only_tool-9.9-py3-none-any.whl", hash = "sha256:0000"}]\n'
)


class RealVenvHost(cls.Host):
    """Runs processes for real, as the test's own account."""

    def __init__(self) -> None:
        self.ran: list[list[str]] = []

    def is_root(self) -> bool:
        return True

    def run(self, cmd, *, user=None, cwd=None, input=None, check=True):  # type: ignore[override]
        self.ran.append(list(cmd))
        result = subprocess.run(cmd, cwd=cwd, input=input, capture_output=True)
        if check and result.returncode != 0:
            raise cls.Refused(
                f"failed: {cmd}: {result.stderr.decode(errors='replace')}"
            )
        return result


def _deploy(
    tmp_path: Path, sha: str, wheel: Path, recorded_sha: str | None = None
) -> None:
    """Lay *wheel* out as release *sha* the way core-deploy does; make it live."""
    core = tmp_path / "core"
    release = core / "releases" / sha
    (release / "venv").mkdir(parents=True)
    record = {
        "sha": sha,
        "wheel_sha256": recorded_sha or hashlib.sha256(wheel.read_bytes()).hexdigest(),
    }
    (release / "venv" / "core-release.json").write_text(json.dumps(record) + "\n")
    (release / "dist").mkdir()
    shutil.copyfile(wheel, release / "dist" / wheel.name)
    (release / "dist" / "poetry.lock").write_bytes(LOCK)
    current = core / "current"
    if current.is_symlink():
        current.unlink()
    current.symlink_to(Path("releases") / sha)


def _setup(tmp_path: Path, host: RealVenvHost) -> object:
    layout = cls.Layout(
        law_home=tmp_path / "core-law", repo=tmp_path, core_root=tmp_path / "core"
    )
    layout.build.mkdir(parents=True, exist_ok=True)
    return cls.Setup(
        layout=layout,
        host=host,
        governor="darek",
        apply=True,
        pip_source=("--no-index",),
    )


def _core_admin(layout: object) -> str:
    done = subprocess.run(
        [str(layout.venv / "bin" / "core-admin")],  # type: ignore[attr-defined]
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_installed_core_admin_runs_from_the_final_path(tmp_path: Path) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel, sha = _wheel(wheels, "2.14.0", "release A")
    _deploy(tmp_path, "a" * 40, wheel)
    host = RealVenvHost()
    setup = _setup(tmp_path, host)

    setup.venv()

    layout = setup.layout
    assert _core_admin(layout) == "release A"
    shebang = (layout.venv / "bin" / "core-admin").read_text().splitlines()[0]
    assert shebang == f"#!{layout.venv}/bin/python"
    assert not layout.venv.with_name("venv.new").exists()
    assert ["--require-hashes"] == [a for a in host.ran[-2] if a == "--require-hashes"]
    assert cls.installed_wheel_sha256(layout.venv) == sha  # pip's own record
    assert (
        json.loads((layout.venv / "core-release.json").read_text())["sha"] == "a" * 40
    )
    assert cls.venv_problems(layout.venv, cls.live_release(layout)) == []


def test_a_wheel_that_is_not_the_recorded_one_is_refused_before_the_swap(
    tmp_path: Path,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel_a, _sha = _wheel(wheels, "2.14.0", "release A")
    _deploy(tmp_path, "a" * 40, wheel_a)
    host = RealVenvHost()
    _setup(tmp_path, host).venv()

    # Release B's record names another hash than the wheel it keeps.
    wheel_b, _sha_b = _wheel(wheels, "2.15.0", "release B")
    _deploy(tmp_path, "b" * 40, wheel_b, recorded_sha="0" * 64)
    setup = _setup(tmp_path, host)
    with pytest.raises(cls.Refused, match="not the wheel core-deploy built"):
        setup.venv()

    assert _core_admin(setup.layout) == "release A"
    assert not setup.layout.venv.with_name("venv.old").exists()


def test_an_entry_point_that_does_not_run_restores_the_previous_venv(
    tmp_path: Path,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel_a, _sha = _wheel(wheels, "2.14.0", "release A")
    _deploy(tmp_path, "a" * 40, wheel_a)
    host = RealVenvHost()
    _setup(tmp_path, host).venv()

    broken, _sha_broken = _wheel(wheels, "2.15.0", "unused")
    # Rewrite the console script to a module that does not exist.
    with zipfile.ZipFile(broken) as zf:
        members = {n: zf.read(n) for n in zf.namelist()}
    members["core_runtime-2.15.0.dist-info/entry_points.txt"] = (
        b"[console_scripts]\ncore-admin = no_such_module:app\n"
    )
    broken.unlink()
    with zipfile.ZipFile(broken, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    _deploy(tmp_path, "b" * 40, broken)
    setup = _setup(tmp_path, host)
    with pytest.raises(cls.Refused, match="previous venv was restored"):
        setup.venv()
    assert _core_admin(setup.layout) == "release A"
    assert (
        json.loads((setup.layout.venv / "core-release.json").read_text())["sha"]
        == "a" * 40
    )


@pytest.mark.skipif(
    not Path("/usr/sbin/visudo").exists(), reason="visudo not installed"
)
def test_sudoers_text_passes_visudo_and_always_asks(tmp_path: Path) -> None:
    text = cls.sudoers_text("darek", Path("/opt/core-law/venv"))
    assert "Defaults>core-law timestamp_timeout=0" in text
    path = tmp_path / "core-law"
    path.write_text(text)
    path.chmod(0o440)
    done = subprocess.run(
        ["/usr/sbin/visudo", "-c", "-f", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    bad = tmp_path / "bad"
    bad.write_text(text.replace("timestamp_timeout=0", "timestamp_timeout=zero"))
    assert (
        subprocess.run(
            ["/usr/sbin/visudo", "-c", "-f", str(bad)], capture_output=True, check=False
        ).returncode
        != 0
    )


def test_a_rule_without_the_fresh_password_is_refused(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        cls,
        "sudoers_text",
        lambda governor, venv: f"{governor} ALL=(core-law) {venv}/bin/x\n",
    )
    setup = cls.Setup(
        layout=cls.Layout(law_home=tmp_path / "l", sudoers=tmp_path / "s"),
        host=SimpleNamespace(),
        governor="darek",
        apply=True,
    )
    with pytest.raises(cls.Refused, match="every time"):
        setup.sudoers()
    assert not (tmp_path / "s").exists()
    shutil.rmtree(tmp_path / "l", ignore_errors=True)
