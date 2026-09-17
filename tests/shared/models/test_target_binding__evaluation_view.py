# tests/shared/models/test_target_binding__evaluation_view.py

"""evaluation_view: the subject-only root an evaluation may read (ADR-159
Note 2026-09-17, ruling M2)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from shared.models.target_binding import DisplacedFile, TargetBinding, evaluation_view


def _binding(tmp_path: Path) -> TargetBinding:
    return TargetBinding(
        subject_path=str(tmp_path / "subject"),
        subject_sha="a" * 40,
        subject_tree_hash="b" * 40,
        bound_repo_path=str(tmp_path / "copy"),
        bound_sha="c" * 40,
        bound_tree_hash="d" * 40,
        floor_hash="e" * 64,
        overlay_hash="f" * 64,
        displaced=(DisplacedFile(".intent/META/vocabulary.json", "1" * 64, "2" * 64),),
    )


def test_bound_context_yields_the_original_subject_and_names_the_exclusions(
    tmp_path: Path,
) -> None:
    ctx = SimpleNamespace(
        target_binding=_binding(tmp_path),
        git_service=SimpleNamespace(repo_path=tmp_path / "copy"),
    )
    root, view = evaluation_view(ctx)
    assert root == tmp_path / "subject"
    assert view["scope"] == "subject"
    assert view["subject_sha"] == "a" * 40
    assert view["apparatus_excluded"] == {
        "execution_copy": str(tmp_path / "copy"),
        "floor_hash": "e" * 64,
        "overlay_hash": "f" * 64,
        "displaced_paths": [".intent/META/vocabulary.json"],
    }


def test_unbound_context_yields_the_repository(tmp_path: Path) -> None:
    ctx = SimpleNamespace(git_service=SimpleNamespace(repo_path=tmp_path))
    root, view = evaluation_view(ctx)
    assert root == tmp_path
    assert view == {"scope": "repository", "root": str(tmp_path)}
