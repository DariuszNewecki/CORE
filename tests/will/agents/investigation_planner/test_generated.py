from __future__ import annotations

from will.agents.investigation_planner import InvestigationPlanError


# ID: ca9ee43b-44c7-4161-8fa3-da76bb21c2b1
def test_InvestigationPlanError():
    message = "investigation plan is not read-only"
    error = InvestigationPlanError(message)

    assert isinstance(error, Exception)
    assert str(error) == message
    assert error.args == (message,)


from will.agents.investigation_planner import InvestigationStep


# ID: 689c595f-7d81-4d69-b22f-c1ba7ad902a7
def test_InvestigationStep():
    step = InvestigationStep(
        step="gather_logs",
        action="read_file",
        params={"path": "/var/log/app.log", "lines": 100},
    )

    assert step.step == "gather_logs"
    assert step.action == "read_file"
    assert step.params == {"path": "/var/log/app.log", "lines": 100}
    assert isinstance(step.params, dict)
