"""Regression test for #270: FileService stores resolved repo_path.

Before #270, ``self.repo_path`` was stored as-passed; if the caller
supplied a symlinked or otherwise unresolved path, downstream callers
that compared against resolved paths (e.g. ``Path.relative_to`` on a
PathResolver-derived directory) raised ValueError. ``__init__`` now
stores ``Path(repo_path).resolve()``.

ADR-097 step 7 narrowed FileService away from carrying its own
``reports_dir`` — the original #270 test asserted against that
attribute, this version asserts the underlying ``repo_path``
resolution invariant directly.
"""

from __future__ import annotations

from pathlib import Path

from body.services.file_service import FileService


def test_file_service_resolves_symlinked_repo_path(tmp_path: Path) -> None:
    """A symlinked repo_path is stored in resolved form."""
    real_repo = tmp_path / "real_repo"
    real_repo.mkdir()
    link = tmp_path / "link_to_repo"
    link.symlink_to(real_repo)

    assert link != real_repo

    service = FileService(link)
    assert service.repo_path == real_repo.resolve()


def test_file_service_resolves_relative_repo_path(
    tmp_path: Path, monkeypatch
) -> None:
    """A relative-form repo_path is stored as an absolute resolved path."""
    real_repo = tmp_path / "rel_repo"
    real_repo.mkdir()

    monkeypatch.chdir(tmp_path)
    service = FileService(Path("rel_repo"))

    assert service.repo_path.is_absolute()
    assert service.repo_path == real_repo.resolve()
