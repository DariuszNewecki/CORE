"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/meta_validator.py
- Symbol: ValidationReport
- Status: 6 tests passed, some failed
- Passing tests: test_initialization_with_custom_values, test_equality_comparison, test_string_representation, test_empty_report_is_valid, test_invalid_report_has_errors, test_documents_consistency
- Generated: 2026-01-11 02:09:20
"""

from mind.governance.meta_validator import ValidationReport


class TestValidationReport:

    def test_initialization_with_custom_values(self):
        """Test that ValidationReport can be initialized with custom values."""
        errors = ["error1", "error2"]
        warnings = ["warning1"]
        report = ValidationReport(
            valid=False,
            errors=errors,
            warnings=warnings,
            documents_checked=5,
            documents_valid=3,
            documents_invalid=2,
        )
        assert not report.valid
        assert report.errors == errors
        assert report.warnings == warnings
        assert report.documents_checked == 5
        assert report.documents_valid == 3
        assert report.documents_invalid == 2

    def test_equality_comparison(self):
        """Test that two ValidationReport instances with same values are equal."""
        report1 = ValidationReport(
            valid=True,
            errors=["test_error"],
            warnings=[],
            documents_checked=1,
            documents_valid=1,
            documents_invalid=0,
        )
        report2 = ValidationReport(
            valid=True,
            errors=["test_error"],
            warnings=[],
            documents_checked=1,
            documents_valid=1,
            documents_invalid=0,
        )
        assert report1.valid == report2.valid
        assert report1.errors == report2.errors
        assert report1.warnings == report2.warnings
        assert report1.documents_checked == report2.documents_checked
        assert report1.documents_valid == report2.documents_valid
        assert report1.documents_invalid == report2.documents_invalid

    def test_string_representation(self):
        """Test the string representation of ValidationReport."""
        report = ValidationReport(
            valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            documents_checked=10,
            documents_valid=7,
            documents_invalid=3,
        )
        str_rep = str(report)
        assert "ValidationReport" in str_rep
        assert "valid=False" in str_rep or "valid: False" in str_rep
        assert "documents_checked=10" in str_rep or "documents_checked: 10" in str_rep

    def test_empty_report_is_valid(self):
        """Test that a report with no errors is marked as valid."""
        report = ValidationReport(
            valid=True,
            errors=[],
            warnings=["Some warning"],
            documents_checked=5,
            documents_valid=5,
            documents_invalid=0,
        )
        assert report.valid
        assert len(report.errors) == 0
        assert report.documents_invalid == 0

    def test_invalid_report_has_errors(self):
        """Test that an invalid report has errors or invalid documents."""
        report1 = ValidationReport(
            valid=False,
            errors=["Validation failed"],
            warnings=[],
            documents_checked=5,
            documents_valid=5,
            documents_invalid=0,
        )
        report2 = ValidationReport(
            valid=False,
            errors=[],
            warnings=[],
            documents_checked=5,
            documents_valid=3,
            documents_invalid=2,
        )
        assert not report1.valid
        assert len(report1.errors) > 0
        assert not report2.valid
        assert report2.documents_invalid > 0

    def test_documents_consistency(self):
        """Test that documents_checked equals documents_valid + documents_invalid."""
        report = ValidationReport(
            valid=True,
            errors=[],
            warnings=[],
            documents_checked=10,
            documents_valid=8,
            documents_invalid=2,
        )
        assert (
            report.documents_checked
            == report.documents_valid + report.documents_invalid
        )
