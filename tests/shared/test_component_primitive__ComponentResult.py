"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/component_primitive.py
- Symbol: ComponentResult
- Status: 15 tests passed, some failed
- Passing tests: test_initialization_with_minimal_required_fields, test_validation_empty_component_id, test_validation_non_string_component_id, test_validation_data_not_dict, test_validation_confidence_below_zero, test_validation_confidence_above_one, test_edge_case_confidence_zero, test_edge_case_confidence_one, test_edge_case_confidence_midpoint, test_metadata_default_factory_creates_new_dict, test_data_can_be_empty_dict, test_data_can_contain_complex_structures, test_next_suggested_can_be_non_empty, test_duration_sec_can_be_set, test_ok_boolean_values
- Generated: 2026-01-11 00:59:07
"""

import pytest

from shared.component_primitive import ComponentPhase, ComponentResult


class TestComponentResult:

    def test_initialization_with_minimal_required_fields(self):
        """Test that ComponentResult can be created with only required fields."""
        result = ComponentResult(
            component_id="test_component",
            ok=True,
            data={"key": "value"},
            phase=ComponentPhase.EXECUTION,
        )
        assert result.component_id == "test_component"
        assert result.ok
        assert result.data == {"key": "value"}
        assert result.phase == ComponentPhase.EXECUTION
        assert result.confidence == 1.0
        assert result.next_suggested == ""
        assert result.metadata == {}
        assert result.duration_sec == 0.0

    def test_validation_empty_component_id(self):
        """Test that empty component_id raises ValueError."""
        with pytest.raises(
            ValueError, match="ComponentResult.component_id must be non-empty string"
        ):
            ComponentResult(
                component_id="", ok=True, data={}, phase=ComponentPhase.EXECUTION
            )

    def test_validation_non_string_component_id(self):
        """Test that non-string component_id raises ValueError."""
        with pytest.raises(
            ValueError, match="ComponentResult.component_id must be non-empty string"
        ):
            ComponentResult(
                component_id=123, ok=True, data={}, phase=ComponentPhase.EXECUTION
            )

    def test_validation_data_not_dict(self):
        """Test that non-dict data raises ValueError."""
        with pytest.raises(ValueError, match=r"ComponentResult.data must be dict"):
            ComponentResult(
                component_id="test",
                ok=True,
                data="not a dict",
                phase=ComponentPhase.EXECUTION,
            )

    def test_validation_confidence_below_zero(self):
        """Test that confidence < 0.0 raises ValueError."""
        with pytest.raises(
            ValueError, match="ComponentResult.confidence must be in \\[0.0, 1.0\\]"
        ):
            ComponentResult(
                component_id="test",
                ok=True,
                data={},
                phase=ComponentPhase.EXECUTION,
                confidence=-0.1,
            )

    def test_validation_confidence_above_one(self):
        """Test that confidence > 1.0 raises ValueError."""
        with pytest.raises(
            ValueError, match="ComponentResult.confidence must be in \\[0.0, 1.0\\]"
        ):
            ComponentResult(
                component_id="test",
                ok=True,
                data={},
                phase=ComponentPhase.EXECUTION,
                confidence=1.1,
            )

    def test_edge_case_confidence_zero(self):
        """Test that confidence of 0.0 is valid."""
        result = ComponentResult(
            component_id="test",
            ok=True,
            data={},
            phase=ComponentPhase.EXECUTION,
            confidence=0.0,
        )
        assert result.confidence == 0.0

    def test_edge_case_confidence_one(self):
        """Test that confidence of 1.0 is valid."""
        result = ComponentResult(
            component_id="test",
            ok=True,
            data={},
            phase=ComponentPhase.EXECUTION,
            confidence=1.0,
        )
        assert result.confidence == 1.0

    def test_edge_case_confidence_midpoint(self):
        """Test that confidence of 0.5 is valid."""
        result = ComponentResult(
            component_id="test",
            ok=True,
            data={},
            phase=ComponentPhase.EXECUTION,
            confidence=0.5,
        )
        assert result.confidence == 0.5

    def test_metadata_default_factory_creates_new_dict(self):
        """Test that default_factory creates independent dict instances."""
        result1 = ComponentResult(
            component_id="test1", ok=True, data={}, phase=ComponentPhase.EXECUTION
        )
        result2 = ComponentResult(
            component_id="test2", ok=False, data={}, phase=ComponentPhase.EXECUTION
        )
        result1.metadata["test"] = "value"
        assert result1.metadata == {"test": "value"}
        assert result2.metadata == {}

    def test_data_can_be_empty_dict(self):
        """Test that data can be an empty dictionary."""
        result = ComponentResult(
            component_id="test", ok=True, data={}, phase=ComponentPhase.EXECUTION
        )
        assert result.data == {}

    def test_data_can_contain_complex_structures(self):
        """Test that data can contain nested structures."""
        complex_data = {
            "list": [1, 2, 3],
            "nested_dict": {"a": {"b": "c"}},
            "tuple": (1, 2, 3),
            "string": "test",
        }
        result = ComponentResult(
            component_id="test",
            ok=True,
            data=complex_data,
            phase=ComponentPhase.EXECUTION,
        )
        assert result.data == complex_data

    def test_next_suggested_can_be_non_empty(self):
        """Test that next_suggested can contain a component name."""
        result = ComponentResult(
            component_id="current",
            ok=True,
            data={},
            phase=ComponentPhase.EXECUTION,
            next_suggested="next_component",
        )
        assert result.next_suggested == "next_component"

    def test_duration_sec_can_be_set(self):
        """Test that duration_sec can be set to various values."""
        result = ComponentResult(
            component_id="test",
            ok=True,
            data={},
            phase=ComponentPhase.EXECUTION,
            duration_sec=123.456,
        )
        assert result.duration_sec == 123.456

    def test_ok_boolean_values(self):
        """Test that ok field accepts both True and False."""
        result_true = ComponentResult(
            component_id="test1", ok=True, data={}, phase=ComponentPhase.EXECUTION
        )
        result_false = ComponentResult(
            component_id="test2", ok=False, data={}, phase=ComponentPhase.EXECUTION
        )
        assert result_true.ok
        assert not result_false.ok
