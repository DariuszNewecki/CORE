from __future__ import annotations

from will.workers.violation_remediator_body.models import _RemediationPlan


# ID: ce3dce84-9354-402b-a303-f0efadd8a89d
class TestRemediationPlan:
    """Test suite for _RemediationPlan data class."""

    # ID: e4eff856-8114-43b3-ac39-bc4b01202b42
    def test_remediation_plan_creation_with_all_fields(self) -> None:
        """Test creating a _RemediationPlan instance with all required fields."""
        plan = _RemediationPlan(
            file_path="src/example.py",
            original_source="def foo(): pass",
            baseline_sha="abc123",
            violations_summary="2 violations found",
            architectural_context={"role": "service", "strategies": ["refactor"]},
            context_text="Some context",
        )
        assert plan.file_path == "src/example.py"
        assert plan.original_source == "def foo(): pass"
        assert plan.baseline_sha == "abc123"
        assert plan.violations_summary == "2 violations found"
        assert plan.architectural_context == {
            "role": "service",
            "strategies": ["refactor"],
        }
        assert plan.context_text == "Some context"

    # ID: 17210bb6-8fd4-40fc-94b0-aaca96841288
    def test_remediation_plan_default_string_fields(self) -> None:
        """Test that string fields accept empty strings as valid values."""
        plan = _RemediationPlan(
            file_path="",
            original_source="",
            baseline_sha="",
            violations_summary="",
            architectural_context={},
            context_text="",
        )
        assert plan.file_path == ""
        assert plan.original_source == ""
        assert plan.baseline_sha == ""
        assert plan.violations_summary == ""
        assert plan.architectural_context == {}
        assert plan.context_text == ""

    # ID: 3f6edded-644c-49a3-8722-43cdb9fc6ef0
    def test_remediation_plan_architectural_context_empty_dict(self) -> None:
        """Test with an empty architectural context dictionary."""
        plan = _RemediationPlan(
            file_path="src/module.py",
            original_source="import os",
            baseline_sha="def456",
            violations_summary="No violations",
            architectural_context={},
            context_text="Clean file",
        )
        assert plan.architectural_context == {}

    # ID: e92a361b-6a81-4eb0-91ae-3dbdc26886f0
    def test_remediation_plan_architectural_context_complex(self) -> None:
        """Test with a complex nested architectural context."""
        complex_context = {
            "role": "controller",
            "responsibilities": ["routing", "validation"],
            "strategies": [
                {"name": "extract_method", "confidence": 0.85},
                {"name": "rename_class", "confidence": 0.72},
            ],
            "metrics": {"lines_of_code": 120, "complexity": 15},
        }
        plan = _RemediationPlan(
            file_path="src/api/handler.py",
            original_source="class Handler: ...",
            baseline_sha="ghi789",
            violations_summary="3 style warnings",
            architectural_context=complex_context,
            context_text="Complex handler with multiple responsibilities",
        )
        assert plan.architectural_context == complex_context

    # ID: 58332425-acac-407b-a79a-e96ad2a5e99b
    def test_remediation_plan_fields_are_mutable(self) -> None:
        """Test that fields are mutable (not frozen)."""
        plan = _RemediationPlan(
            file_path="initial.py",
            original_source="v1",
            baseline_sha="sha1",
            violations_summary="none",
            architectural_context={"key": "value"},
            context_text="initial",
        )
        plan.file_path = "updated.py"
        plan.original_source = "v2"
        plan.baseline_sha = "sha2"
        plan.violations_summary = "1 violation"
        plan.architectural_context = {"new_key": "new_value"}
        plan.context_text = "updated"
        assert plan.file_path == "updated.py"
        assert plan.original_source == "v2"
        assert plan.baseline_sha == "sha2"
        assert plan.violations_summary == "1 violation"
        assert plan.architectural_context == {"new_key": "new_value"}
        assert plan.context_text == "updated"

    # ID: 7c07dfe2-6bd3-42d6-b428-0f3815b80310
    def test_remediation_plan_type_hints(self) -> None:
        """Verify that type hints are consistent with expected types."""
        plan = _RemediationPlan(
            file_path="test.py",
            original_source="source",
            baseline_sha="sha",
            violations_summary="summary",
            architectural_context={"role": "test"},
            context_text="text",
        )
        assert isinstance(plan.file_path, str)
        assert isinstance(plan.original_source, str)
        assert isinstance(plan.baseline_sha, str)
        assert isinstance(plan.violations_summary, str)
        assert isinstance(plan.architectural_context, dict)
        assert isinstance(plan.context_text, str)

    # ID: b2bdee47-ed68-4998-b18e-80141d971834
    def test_remediation_plan_repr(self) -> None:
        """Test the string representation is usable (no exception)."""
        plan = _RemediationPlan(
            file_path="test_repr.py",
            original_source="def test(): pass",
            baseline_sha="repr_sha",
            violations_summary="0 violations",
            architectural_context={"info": "data"},
            context_text="Repr test",
        )
        repr_str = repr(plan)
        assert "file_path" in repr_str or "_RemediationPlan" in repr_str

    # ID: 8f42234a-dc1d-400a-9ebb-a1e91821e501
    def test_remediation_plan_equality(self) -> None:
        """Test that two equal instances compare equal and unequal ones don't."""
        plan_a = _RemediationPlan(
            file_path="same.py",
            original_source="code",
            baseline_sha="sha",
            violations_summary="summary",
            architectural_context={"key": "value"},
            context_text="text",
        )
        plan_b = _RemediationPlan(
            file_path="same.py",
            original_source="code",
            baseline_sha="sha",
            violations_summary="summary",
            architectural_context={"key": "value"},
            context_text="text",
        )
        plan_c = _RemediationPlan(
            file_path="different.py",
            original_source="code",
            baseline_sha="sha",
            violations_summary="summary",
            architectural_context={"key": "value"},
            context_text="text",
        )
        assert plan_a == plan_b
        assert plan_a != plan_c
