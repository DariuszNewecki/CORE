"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/component_primitive.py
- Symbol: Component
- Status: 8 tests passed, some failed
- Passing tests: test_component_id_default_implementation, test_component_id_override_behavior, test_phase_must_be_implemented, test_description_from_docstring, test_description_no_docstring, test_description_empty_docstring, test_execute_must_be_implemented, test_abstract_nature_of_base_class
- Generated: 2026-01-11 00:59:40
"""

import pytest

from shared.component_primitive import Component, ComponentPhase


class TestComponent:

    def test_component_id_default_implementation(self):
        """Test that component_id returns lowercase class name by default."""

        class TestConcreteComponent(Component):

            @property
            def phase(self):
                return ComponentPhase.EXECUTION

        component = TestConcreteComponent()
        assert component.component_id == "testconcretecomponent"

    def test_component_id_override_behavior(self):
        """Test that component_id can be overridden by subclasses."""

        class CustomIDComponent(Component):

            @property
            def component_id(self):
                return "custom-id"

            @property
            def phase(self):
                return ComponentPhase.EXECUTION

        component = CustomIDComponent()
        assert component.component_id == "custom-id"

    def test_phase_must_be_implemented(self):
        """Test that phase property raises NotImplementedError if not overridden."""

        class IncompleteComponent(Component):
            pass

        component = IncompleteComponent()
        with pytest.raises(NotImplementedError) as exc_info:
            _ = component.phase
        assert "must declare its phase" in str(exc_info.value)

    def test_description_from_docstring(self):
        """Test that description extracts first line from docstring."""

        class DocumentedComponent(Component):
            """This is a test component description.

            Additional details here should be ignored.
            """

            @property
            def phase(self):
                return ComponentPhase.EXECUTION

        component = DocumentedComponent()
        assert component.description == "This is a test component description."

    def test_description_no_docstring(self):
        """Test that description returns default when no docstring exists."""

        class NoDocComponent(Component):

            @property
            def phase(self):
                return ComponentPhase.EXECUTION

        component = NoDocComponent()
        assert component.description == "No description"

    def test_description_empty_docstring(self):
        """Test that description handles empty docstring."""

        class EmptyDocComponent(Component):
            """"""

            @property
            def phase(self):
                return ComponentPhase.EXECUTION

        component = EmptyDocComponent()
        assert component.description == "No description"

    def test_abstract_nature_of_base_class(self):
        """Test that Component cannot be instantiated directly due to abstract phase property."""
        component = Component()
        with pytest.raises(NotImplementedError):
            _ = component.phase
