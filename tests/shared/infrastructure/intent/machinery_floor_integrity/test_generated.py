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


from shared.infrastructure.intent.machinery_floor_integrity import FloorIntegrityReport


# ID: feeb569d-175a-4584-9c5c-a3d869894961
def test_FloorIntegrityReport():
    report = FloorIntegrityReport(
        ok=("META/enums.json", "META/policy.json"),
        modified=(),
        missing=(),
    )
    assert report.clean is True
    assert "modified" not in report.describe()
    assert "missing" not in report.describe()
    assert "all byte-identical to the shipped floor" in report.describe()
    assert "floor files: 2" in report.describe()

    dirty = FloorIntegrityReport(
        ok=("META/enums.json",),
        modified=("META/policy.json",),
        missing=("META/roles.json",),
    )
    assert dirty.clean is False
    desc = dirty.describe()
    assert "modified: META/policy.json" in desc
    assert "missing: META/roles.json" in desc
    assert "all byte-identical to the shipped floor" not in desc
    assert "floor files: 3" in desc


from shared.infrastructure.intent.machinery_floor_integrity import verify_floor


# ID: e01bcdc5-f5e4-4a2c-a25d-a34b11c33c56
def test_verify_floor(tmp_path: Path) -> None:
    intent_root = tmp_path / ".intent"
    intent_root.mkdir()

    # A floor file that exists and is byte-identical -> ok
    ok_file = intent_root / "a.txt"
    ok_file.write_bytes(b"hello")
    # A floor file that exists with different bytes -> modified
    modified_file = intent_root / "b.txt"
    modified_file.write_bytes(b"changed")

    manifest = {
        "a.txt": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",  # sha256("hello")
        "b.txt": "0" * 64,  # deliberately different from actual content
        "c.txt": "1" * 64,  # not present -> missing
    }

    with patch(
        "shared.infrastructure.intent.machinery_floor_integrity.floor_manifest",
        return_value=manifest,
    ):
        report = verify_floor(intent_root)

    assert report.ok == ("a.txt",)
    assert report.modified == ("b.txt",)
    assert report.missing == ("c.txt",)


# ID: 3bc0ac04-016d-4b53-a16c-fc964fdbdf35
def test_FloorIntegrityReport_describe() -> None:
    report = FloorIntegrityReport(
        ok=["a.py", "b.py"],
        modified=["c.py"],
        missing=["d.py"],
    )
    result = report.describe()
    assert isinstance(result, str)
    assert "floor files: 4" in result
    assert "modified: c.py" in result
    assert "missing: d.py" in result


# ID: f965489e-6e69-44f7-8da8-1ea45ef53d4f
def test_FloorIntegrityReport_clean() -> None:
    report = FloorIntegrityReport(modified=[], missing=[])
    assert report.clean is True
