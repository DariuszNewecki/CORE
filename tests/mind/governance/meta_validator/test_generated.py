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


from mind.governance.meta_validator import MetaValidator


# ID: ed08507d-f2ac-476c-a51b-b70eb99d2afb
def test_MetaValidator(tmp_path):
    with patch("mind.governance.meta_validator.get_intent_repository") as mock_get_repo:
        mock_repo = MagicMock()
        mock_repo.root = tmp_path
        mock_repo.load_document = MagicMock(
            return_value={"scope": {}, "type": "object"}
        )
        mock_repo.resolve_rel = MagicMock(return_value=tmp_path / "meta.json")
        mock_get_repo.return_value = mock_repo

        validator = MetaValidator(intent_root=tmp_path)

    assert validator.repo is mock_repo
    assert validator.intent_root == tmp_path
    assert validator.errors == []
    assert validator.warnings == []
    assert isinstance(validator._all_schemas, dict)
    assert isinstance(validator.meta_schema, dict)
    assert validator._validated_directories is None or isinstance(
        validator._validated_directories, list
    )


from mind.governance.meta_validator import ValidationReport


# ID: a20f9472-9630-4e80-b68c-84c19ce44ce3
def test_ValidationReport():
    report = ValidationReport(
        valid=True,
        errors=[],
        warnings=[],
        documents_checked=3,
        documents_valid=3,
        documents_invalid=0,
    )

    assert report.valid is True
    assert report.errors == []
    assert report.warnings == []
    assert report.documents_checked == 3
    assert report.documents_valid == 3
    assert report.documents_invalid == 0
    assert report.documents_valid + report.documents_invalid == report.documents_checked


from mind.governance.meta_validator import ValidationError


# ID: 626f7cef-4264-4f2d-b833-2fe9894dc9ed
def test_ValidationError():
    error = ValidationError(
        document="docs/adr/ADR-133.md",
        error_type="missing_field",
        message="Required field 'status' is missing",
    )

    assert error.document == "docs/adr/ADR-133.md"
    assert error.error_type == "missing_field"
    assert error.message == "Required field 'status' is missing"
    assert error.severity == "error"
    assert error.field is None

    explicit_error = ValidationError(
        document="docs/adr/ADR-134.md",
        error_type="invalid_value",
        message="Value must be one of the allowed set",
        severity="warning",
        field="status",
    )

    assert explicit_error.document == "docs/adr/ADR-134.md"
    assert explicit_error.error_type == "invalid_value"
    assert explicit_error.message == "Value must be one of the allowed set"
    assert explicit_error.severity == "warning"
    assert explicit_error.field == "status"
