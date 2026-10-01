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
