from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.infrastructure.intent.machinery_floor_integrity import find_collisions


# ID: fed8cf08-7b97-4514-ab37-d72f0e50408b
def test_find_collisions(tmp_path: Path) -> None:
    intent_root = tmp_path / ".intent"
    intent_root.mkdir()

    fake_report = MagicMock()
    fake_report.modified = ["a.py", "b.py"]

    with patch(
        "shared.infrastructure.intent.machinery_floor_integrity.verify_floor",
        return_value=fake_report,
    ) as mock_verify:
        result = find_collisions(intent_root)

    assert result == ["a.py", "b.py"]
    mock_verify.assert_called_once_with(intent_root)


import hashlib


# ID: f6b361c9-203a-4cec-823e-1a017ea26d81
def test_floor_hash() -> None:
    from shared.infrastructure.intent.machinery_floor_integrity import floor_hash

    manifest = {
        "b/path.py": "bbbb",
        "a/path.py": "aaaa",
    }

    with patch(
        "shared.infrastructure.intent.machinery_floor_integrity.floor_manifest",
        return_value=manifest,
    ):
        result = floor_hash()

    expected = hashlib.sha256()
    for rel, digest in sorted(manifest.items()):
        expected.update(rel.encode("utf-8"))
        expected.update(b"\0")
        expected.update(digest.encode("ascii"))
        expected.update(b"\n")

    assert result == expected.hexdigest()
    assert isinstance(result, str)
    assert len(result) == 64




# ID: a159d1e0-e838-4fd5-9bbe-cd9a24b95f20
def test_floor_manifest(tmp_path: Path):
    from shared.infrastructure.intent.machinery_floor_integrity import floor_manifest

    floor_file = tmp_path / "floors" / "level_1.yaml"
    floor_file.parent.mkdir(parents=True, exist_ok=True)
    floor_file.write_text("content: hello\n", encoding="utf-8")

    with (
        patch(
            "shared.infrastructure.intent.machinery_floor_integrity._floor_root",
            return_value=tmp_path / "floors",
        ),
        patch(
            "shared.infrastructure.intent.machinery_floor_integrity._iter_floor_files",
            return_value=[floor_file],
        ),
        patch(
            "shared.infrastructure.intent.machinery_floor_integrity._sha256_file",
            return_value="abc123",
        ),
    ):
        result = floor_manifest()

    assert result == {"level_1.yaml": "abc123"}
