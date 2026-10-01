from __future__ import annotations

import pytest

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck


# ID: c11e5d13-8085-400d-aa4d-63f33d6c0b91
def test_WorkflowCheck__verify():
    class _Concrete(WorkflowCheck):
        # ID: a8f4b818-748c-4dd3-83a0-c34c877a1701
        async def verify(self, file_path, params):
            return []

    check = _Concrete()
    result = check.verify.__self__ if hasattr(check.verify, "__self__") else check
    assert result is check

    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            WorkflowCheck.verify(check, None, {})
        )


from collections.abc import Sequence
from typing import Any


# ID: 5412ebd9-b0e1-467c-ac58-abaa6a02fd06
def test_WorkflowCheck() -> None:
    # A minimal concrete subclass implementing the abstract `verify` method.
    class _ConcreteCheck(WorkflowCheck):
        check_type = "example"

        # ID: ec433e03-66a4-4d99-b995-fc3d24b62213
        async def verify(self, file_path, params) -> Sequence[str | Any]:
            return []

    check = _ConcreteCheck()

    # Concrete subclass is instantiable and carries the declared check_type.
    assert isinstance(check, WorkflowCheck)
    assert check.check_type == "example"

    # The abstract base cannot be instantiated directly.
    with pytest.raises(TypeError):
        WorkflowCheck()  # type: ignore[abstract]

    # `verify` is an abstractmethod on the base class.
    assert "verify" in WorkflowCheck.__abstractmethods__

    # Happy path: calling verify returns an empty sequence (no violations).
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        check.verify(file_path=None, params={})
    )
    assert list(result) == []
