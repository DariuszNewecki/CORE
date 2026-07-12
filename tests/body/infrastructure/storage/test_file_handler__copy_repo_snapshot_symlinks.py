"""copy_repo_snapshot preserves symlinks instead of dereferencing them.

ADR-147 follow-up (b). A repo-root symlink (e.g. an external data mount)
must be recreated as a symlink in the snapshot, not copied by content —
dereferencing balloons the snapshot (the ITAM incident) and can pull
out-of-repo bytes into scratch. Pins symlinks=True on the snapshot copytree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler


# ID: 98123d9b-3b1d-4960-92bc-f97dd51f59f7
def test_copy_repo_snapshot_preserves_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Repo root with a real file, a real dir, and a top-level symlink to that dir.
    (tmp_path / "real.txt").write_text("x\n", encoding="utf-8")
    target_dir = tmp_path / "realdir"
    target_dir.mkdir()
    (target_dir / "inner.txt").write_text("y\n", encoding="utf-8")
    (tmp_path / "linkdir").symlink_to(target_dir, target_is_directory=True)

    fh = FileHandler(str(tmp_path))
    monkeypatch.setattr(fh, "_guard_paths", lambda *args, **kwargs: None)

    # Destination under the excluded `var/` prefix so the copytree walk does not
    # recurse into its own output.
    fh.copy_repo_snapshot("var/snapshot")

    snap = tmp_path / "var" / "snapshot"
    # The fix: the symlink is recreated as a symlink, NOT dereferenced into a
    # real directory. Without symlinks=True this assertion fails (is_symlink()
    # is False because copytree copied the target's content).
    assert (snap / "linkdir").is_symlink(), (
        "ADR-147 (b): root symlink must be preserved, not dereferenced"
    )
    assert (snap / "real.txt").read_text(encoding="utf-8") == "x\n"
