from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.governance.specs_doc_validator import SpecsDocValidator


# ID: ee767e4d-5b9f-464c-ba25-257c4e4a33e5
def test_SpecsDocValidator_validate_all_documents(tmp_path):
    with patch(
        "mind.governance.specs_doc_validator.get_intent_repository"
    ) as mock_get_repo:
        intent_root = tmp_path / ".specs"
        intent_root.mkdir()
        mock_repo = MagicMock()
        mock_repo.root = intent_root
        mock_get_repo.return_value = mock_repo

        validator = SpecsDocValidator(repo_root=tmp_path)

        doc_path = tmp_path / "docs" / "example.spec.md"
        doc_path.parent.mkdir(parents=True)
        doc_path.write_text("---\ntitle: hi\n---\nbody\n", encoding="utf-8")

        schema = {"type": "object"}

        validator._modeled_types = MagicMock(
            return_value=[("example", ["docs/*.spec.md"], "example.schema.json")]
        )
        validator._load_schema = MagicMock(return_value=schema)
        validator.validate_header = MagicMock(return_value=[])

        with (
            patch(
                "mind.governance.specs_doc_validator.law_glob",
                return_value=[doc_path],
            ),
            patch(
                "mind.governance.specs_doc_validator.law_relpath",
                return_value="docs/example.spec.md",
            ),
            patch(
                "mind.governance.specs_doc_validator.parse_frontmatter",
                return_value={"title": "hi"},
            ),
        ):
            report = validator.validate_all_documents()

        assert report.valid is True
        assert report.errors == []
        assert report.warnings == []
        assert report.documents_checked == 1
        assert report.documents_valid == 1
        assert report.documents_invalid == 0
        validator._load_schema.assert_called_once_with("example.schema.json")
        validator.validate_header.assert_called_once_with(
            schema, {"title": "hi"}, document="docs/example.spec.md"
        )
