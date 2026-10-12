"""core-law-setup's venv step with a real venv and a real installed entry point.

test_core_law_setup.py simulates processes; that hid a real defect: the
venv was built at ``venv.new`` and renamed, and a venv records its own path
in its entry points, so the installed ``core-admin`` pointed at a directory
that no longer existed. Here the venv step runs for real -- ``python -m
venv``, ``pip install`` of a hash-pinned wheel from a local folder, and the
installed ``core-admin`` executed -- and a failing upgrade must put the
previous venv back with its entry point still working. The sudoers text is
checked by the real ``visudo``.

The wheel is a stand-in named core-runtime with a ``core-admin`` console
script; no network. The account switch (``runuser -u core-law``) is the only
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


class RealVenvHost(cls.Host):
    """Runs processes for real, as the test's own account; PyPI is a dict."""

    def __init__(self, pypi: dict[str, str], wheels: Path) -> None:
        self.pypi = pypi
        self.wheels = wheels
        self.ran: list[list[str]] = []

    def is_root(self) -> bool:
        return True

    def fetch(self, url: str, timeout: float = 30.0) -> bytes:
        if url.startswith(cls.PYPI):
            version = url.split("/")[-2]
            return json.dumps(
                {
                    "info": {"version": version},
                    "urls": [
                        {
                            "packagetype": "bdist_wheel",
                            "filename": f"core_runtime-{version}-py3-none-any.whl",
                            "digests": {"sha256": self.pypi[version]},
                        }
                    ],
                }
            ).encode()
        # The stand-in has no runtime dependencies. A dev-only package is
        # listed whose wheel exists nowhere: installing it would fail offline,
        # so a passing install proves dev packages are never attempted.
        return (
            b'[[package]]\nname = "dev-only-tool"\nversion = "9.9"\ngroups = ["dev"]\n'
            b'files = [{file = "dev_only_tool-9.9-py3-none-any.whl", hash = "sha256:0000"}]\n'
        )

    def run(self, cmd, *, user=None, cwd=None, input=None, check=True):  # type: ignore[override]
        self.ran.append(list(cmd))
        result = subprocess.run(cmd, cwd=cwd, input=input, capture_output=True)
        if check and result.returncode != 0:
            raise cls.Refused(
                f"failed: {cmd}: {result.stderr.decode(errors='replace')}"
            )
        return result


def _setup(tmp_path: Path, host: RealVenvHost, version: str) -> object:
    layout = cls.Layout(law_home=tmp_path / "core-law", repo=tmp_path)
    layout.build.mkdir(parents=True, exist_ok=True)
    return cls.Setup(
        layout=layout,
        host=host,
        version=version,
        governor="darek",
        apply=True,
        pip_source=("--no-index", "--find-links", str(host.wheels)),
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
    _wheel_path, sha = _wheel(wheels, "2.14.0", "release 2.14.0")
    host = RealVenvHost({"2.14.0": sha}, wheels)
    setup = _setup(tmp_path, host, "2.14.0")

    setup.venv()

    layout = setup.layout
    assert _core_admin(layout) == "release 2.14.0"
    shebang = (layout.venv / "bin" / "core-admin").read_text().splitlines()[0]
    assert shebang == f"#!{layout.venv}/bin/python"
    assert not layout.venv.with_name("venv.new").exists()
    assert ["--require-hashes"] == [a for a in host.ran[-2] if a == "--require-hashes"]


def test_a_failed_upgrade_restores_the_previous_venv(tmp_path: Path) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    _w, sha_old = _wheel(wheels, "2.14.0", "release 2.14.0")
    host = RealVenvHost({"2.14.0": sha_old}, wheels)
    _setup(tmp_path, host, "2.14.0").venv()

    # 2.15.0's published hash does not match the wheel pip finds: pip refuses.
    _w, _sha_new = _wheel(wheels, "2.15.0", "release 2.15.0")
    host.pypi["2.15.0"] = "0" * 64
    setup = _setup(tmp_path, host, "2.15.0")
    with pytest.raises(cls.Refused, match="previous venv was restored"):
        setup.venv()

    assert _core_admin(setup.layout) == "release 2.14.0"
    assert cls.installed_version(setup.layout.venv) == "2.14.0"
    assert not setup.layout.venv.with_name("venv.old").exists()


def test_an_entry_point_that_does_not_run_restores_the_previous_venv(
    tmp_path: Path,
) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    _w, sha_old = _wheel(wheels, "2.14.0", "release 2.14.0")
    host = RealVenvHost({"2.14.0": sha_old}, wheels)
    _setup(tmp_path, host, "2.14.0").venv()

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
    host.pypi["2.15.0"] = hashlib.sha256(broken.read_bytes()).hexdigest()
    setup = _setup(tmp_path, host, "2.15.0")
    with pytest.raises(cls.Refused, match="previous venv was restored"):
        setup.venv()
    assert _core_admin(setup.layout) == "release 2.14.0"


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
        version="2.14.0",
        governor="darek",
        apply=True,
    )
    with pytest.raises(cls.Refused, match="every time"):
        setup.sudoers()
    assert not (tmp_path / "s").exists()
    shutil.rmtree(tmp_path / "l", ignore_errors=True)
