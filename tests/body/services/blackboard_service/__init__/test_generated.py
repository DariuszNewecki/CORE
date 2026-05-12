import pytest
from src.body.services.blackboard_service import BlackboardService
from src.body.services.blackboard_service.blackboard_service import BlackboardService as BlackboardServiceBase
from src.body.services.blackboard_service.blackboard_proposal_service import BlackboardProposalService


class TestBlackboardService:
    """Test suite for BlackboardService class."""

    def test_class_inheritance(self):
        """Verify BlackboardService inherits from both parent classes."""
        assert issubclass(BlackboardService, BlackboardServiceBase)
        assert issubclass(BlackboardService, BlackboardProposalService)

    def test_instantiation(self):
        """Verify BlackboardService can be instantiated."""
        instance = BlackboardService()
        assert isinstance(instance, BlackboardService)
        assert isinstance(instance, BlackboardServiceBase)
        assert isinstance(instance, BlackboardProposalService)

    def test_is_abstract_class(self):
        """Verify BlackboardService is not abstract (can be instantiated directly)."""
        try:
            instance = BlackboardService()
            assert instance is not None
        except TypeError:
            pytest.fail("BlackboardService should not be abstract")

    def test_method_resolution_order(self):
        """Verify method resolution order is correct."""
        mro = BlackboardService.__mro__
        assert BlackboardService in mro
        assert BlackboardServiceBase in mro
        assert BlackboardProposalService in mro

    @pytest.mark.parametrize("attr", [
        "__init__",
    ])
    def test_required_attributes(self, attr):
        """Verify required attributes exist on the class."""
        assert hasattr(BlackboardService, attr), f"Missing attribute: {attr}"

    def test_dunder_integrity(self):
        """Verify dunder methods are properly inherited."""
        assert BlackboardService.__name__ == "BlackboardService"
        assert BlackboardService.__module__ == "src.body.services.blackboard_service"

    def test_bases_contain_parents(self):
        """Verify bases tuple contains expected parent classes."""
        bases = BlackboardService.__bases__
        assert BlackboardServiceBase in bases
        assert BlackboardProposalService in bases

    def test_instance_of_parents(self):
        """Verify instance is also instance of parent classes."""
        instance = BlackboardService()
        assert isinstance(instance, BlackboardServiceBase)
        assert isinstance(instance, BlackboardProposalService)

    def test_multiple_instantiation(self):
        """Verify multiple instances can be created independently."""
        instance1 = BlackboardService()
        instance2 = BlackboardService()
        assert instance1 is not instance2
        assert type(instance1) is type(instance2)
