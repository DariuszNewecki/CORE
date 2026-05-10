"""Regression test for #270: FileService accepts unresolved repo_path.

PathResolver internally resolves the repo root via Path(...).resolve(), so
``self.reports_dir`` is always a resolved Path. Before #270, ``self.repo_path``
was stored as-passed; if the caller supplied a symlinked or otherwise
unresolved path, ``self.reports_dir.relative_to(self.repo_path)`` raised
ValueError. ``__init__`` now stores ``Path(repo_path).resolve()``.
"""

from __future__ import annotations

from pathlib import Path

from body.services.file_service import FileService


def test_file_service_accepts_symlinked_repo_path(tmp_path: Path) -> None:
    """A symlinked repo_path resolves cleanly; reports_dir.relative_to(repo_path) works."""
    real_repo = tmp_path / "real_repo"
    real_repo.mkdir()
    link = tmp_path / "link_to_repo"
    link.symlink_to(real_repo)

    # Sanity: link and real_repo are different unresolved Paths.
    assert link != real_repo

    service = FileService(link)

    # repo_path is stored resolved; reports_dir.relative_to() does not raise.
    assert service.repo_path == real_repo.resolve()
    rel = service.reports_dir.relative_to(service.repo_path)
    # The specific reports_dir layout is set by PathResolver/registry; what
    # matters here is only that relative_to() returns a valid relative path.
    assert not rel.is_absolute()


def test_file_service_accepts_relative_repo_path(tmp_path: Path, monkeypatch) -> None:
    """A relative-form repo_path resolves cleanly during __init__."""
    real_repo = tmp_path / "rel_repo"
    real_repo.mkdir()

    monkeypatch.chdir(tmp_path)
    service = FileService(Path("rel_repo"))

    assert service.repo_path.is_absolute()
    rel = service.reports_dir.relative_to(service.repo_path)
    assert not rel.is_absolute()
