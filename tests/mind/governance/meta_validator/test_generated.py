from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


# ID: e5e28a4f-7a26-49ae-8dad-e12c4614a2eb
def test_MetaValidator_validate_all_documents(tmp_path: Path) -> None:
    import mind.governance.meta_validator as mv

    validated_root = tmp_path / "intent"
    validated_root.mkdir()

    doc = validated_root / "GLOBAL-DOCUMENT.md"
    doc.write_text("content", encoding="utf-8")

    excluded_dir = validated_root / "excluded"
    excluded_dir.mkdir()
    (excluded_dir / "skip.json").write_text("{}", encoding="utf-8")

    schemas_dir = validated_root / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "schema.json").write_text("{}", encoding="utf-8")

    fake_repo = MagicMock()
    fake_repo.root = validated_root
    artifact = MagicMock()
    artifact.content = {"discovery": ["intent/*.md"]}
    fake_repo.get_artifact_type.return_value = artifact

    meta_schema = {"scope": {"excludes": [".intent/excluded/"]}}

    with (
        patch.object(mv, "get_intent_repository", return_value=fake_repo),
        patch.object(mv.MetaValidator, "_index_all_schemas", return_value={}),
        patch.object(mv.MetaValidator, "_load_meta_schema", return_value=meta_schema),
        patch.object(
            mv.MetaValidator, "_load_validated_directories", return_value=None
        ) as mock_load_dirs,
        patch.object(
            mv.MetaValidator, "_validate_document", return_value=True
        ) as mock_validate,
    ):
        validator = mv.MetaValidator()
        report = validator.validate_all_documents()

    mock_load_dirs.assert_called_once()
    mock_validate.assert_called_once_with(doc, Path("GLOBAL-DOCUMENT.md"))
    assert report.valid is True
    assert report.documents_checked == 1
    assert report.documents_valid == 1
    assert report.documents_invalid == 0
    assert report.errors == []
    assert report.warnings == []
