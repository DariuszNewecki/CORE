from __future__ import annotations

from will.agents.investigation_planner import InvestigationPlanError


# ID: ca9ee43b-44c7-4161-8fa3-da76bb21c2b1
def test_InvestigationPlanError():
    message = "investigation plan is not read-only"
    error = InvestigationPlanError(message)

    assert isinstance(error, Exception)
    assert str(error) == message
    assert error.args == (message,)
