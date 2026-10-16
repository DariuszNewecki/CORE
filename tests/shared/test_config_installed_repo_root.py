# tests/shared/test_config_installed_repo_root.py
"""An installed release never treats its own package directory as the repo (#1064).

In a wheel, ``REPO_ROOT`` (``config.py``'s grandparent) is
``<venv>/lib/python3.X``. Run without REPO_PATH from a directory with no
``.intent/`` above it, the release took that as the repository and tried
to create ``<venv>/lib/python3.X/var`` — a PermissionError for anyone but
the release's owner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import shared.config as config
from shared.config import Settings, resolve_default_repo_path
from shared.infrastructure.intent.law_roots import configured_repo_root


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A wheel layout as REPO_ROOT, and a law-less working directory."""
    lib = tmp_path / "venv" / "lib" / "python3.12"
    (lib / "site-packages" / "shared").mkdir(parents=True)
    (lib / "site-packages" / "shared" / "config.py").touch()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(config, "REPO_ROOT", lib)
    monkeypatch.chdir(work)
    monkeypatch.delenv("REPO_PATH", raising=False)
    return lib, work


# ID: 62c54129-661b-4a23-8077-ec3bec8213a4
def test_installed_release_falls_back_to_the_working_directory(
    installed: tuple[Path, Path],
) -> None:
    lib, work = installed
    assert resolve_default_repo_path() == work
    assert configured_repo_root() == work
    settings = Settings()
    assert settings.REPO_PATH == work
    assert not Path(settings.CORE_ACTION_LOG_PATH).is_relative_to(lib)


# ID: 8aa6c5f9-1a59-4705-9b42-55eefd9803eb
def test_source_tree_still_falls_back_to_itself(tmp_path: Path) -> None:
    (tmp_path / "src" / "shared").mkdir(parents=True)
    (tmp_path / "src" / "shared" / "config.py").touch()
    assert config.fallback_repo_root(tmp_path) == tmp_path
    assert config.fallback_repo_root() == config.REPO_ROOT
