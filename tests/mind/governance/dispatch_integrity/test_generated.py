from __future__ import annotations

from unittest.mock import MagicMock

from mind.governance.dispatch_integrity import declared_check_types


# ID: 39baa4d4-15ce-4421-819e-2ab37f7a2e53
def test_declared_check_types():
    # Happy path 1: engine exposes a supported_check_types() classmethod
    engine_cm = MagicMock()
    engine_cm.supported_check_types = MagicMock(return_value=["a", "b", "a"])
    assert declared_check_types(engine_cm) == frozenset({"a", "b"})
    engine_cm.supported_check_types.assert_called_once_with()

    # Happy path 2: engine exposes a _SUPPORTED_CHECK_TYPES ClassVar instead,
    # and has no callable supported_check_types accessor
    engine_cv = MagicMock(spec=["_SUPPORTED_CHECK_TYPES"])
    engine_cv._SUPPORTED_CHECK_TYPES = ("x", "y")
    assert declared_check_types(engine_cv) == frozenset({"x", "y"})

    # Happy path 3: an EMPTY declaration is still a declaration
    engine_empty = MagicMock(spec=["_SUPPORTED_CHECK_TYPES"])
    engine_empty._SUPPORTED_CHECK_TYPES = ()
    assert declared_check_types(engine_empty) == frozenset()


# ID: 5bf77674-46e4-4683-adf9-d341db3ecbe8
def test_VocabularyUnavailableError():
    from mind.governance.dispatch_integrity import VocabularyUnavailableError

    message = "engine 'x' vocabulary could not be read"
    error = VocabularyUnavailableError(message)

    assert isinstance(error, Exception)
    assert str(error) == message
    assert error.args == (message,)

    raised = False
    try:
        raise VocabularyUnavailableError(message)
    except VocabularyUnavailableError as caught:
        raised = True
        assert caught is not None
        assert str(caught) == message
    assert raised is True
