from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from will.phases.investigation_phase import InvestigationPhase


# ID: a8b02cc1-5981-47c7-b023-673be684cea6
def test_InvestigationPhase():
    context = MagicMock()

    step = SimpleNamespace(action="inspect.layout", params={})
    context.results = {"parse": {"investigation_plan": [step]}}

    finding = MagicMock()
    finding.as_payload = MagicMock(return_value={"path": "", "category": "layout"})

    phase = InvestigationPhase(core_context=MagicMock())
    phase._target_root = MagicMock(return_value=None)
    phase._handlers = MagicMock(
        return_value={"inspect.layout": MagicMock(return_value=[finding])}
    )

    result = asyncio_run(phase.execute(context))

    assert result.name == "runtime"
    assert result.ok is True
    assert result.error == ""
    assert result.data["findings"] == [{"path": "", "category": "layout"}]
    assert result.data["findings_count"] == 1
    assert result.data["steps_executed"] == 1
    assert "unsupported_steps" not in result.data


# ID: ca48dfda-804f-4dc8-b8c5-efbbef093abc
def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)





# ID: bf9f68fb-da99-4694-961b-fd8d83326410
async def test_InvestigationPhase_execute():
    # --- construct the phase under test ---
    phase = InvestigationPhase(core_context=MagicMock())

    # --- build a fake finding object with as_payload() ---
    finding = MagicMock()
    finding.as_payload.return_value = {"kind": "note", "detail": "hello"}

    # --- handler that returns our finding ---
    handler = MagicMock(return_value=[finding])

    # --- patch self._handlers() and self._target_root() ---
    phase._handlers = MagicMock(return_value={"scan": handler})
    phase._target_root = MagicMock(return_value="/tmp/target")

    # --- build a step object with action/params attributes ---
    step = MagicMock()
    step.action = "scan"
    step.params = {"depth": 1}

    # --- build the workflow context ---
    context = MagicMock()
    context.results = {
        "parse": {
            "investigation_plan": [step],
            "reconnaissance": {"raw": {"host": "example"}},
        }
    }

    # --- run the phase ---
    result = await InvestigationPhase.execute(phase, context)

    # --- assertions: happy path ---
    assert result.ok is True
    assert result.name == "runtime"
    assert result.error == ""
    assert result.data["findings_count"] == 1
    assert result.data["steps_executed"] == 1
    assert result.data["findings"] == [{"kind": "note", "detail": "hello"}]
    assert "unsupported_steps" not in result.data

    handler.assert_called_once_with({"host": "example"}, {"depth": 1}, "/tmp/target")
    assert isinstance(result.duration_sec, float)
    assert result.duration_sec >= 0
