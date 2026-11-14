from __future__ import annotations

import pytest


conformance = pytest.importorskip("mind.engine_api.conformance")
ConformanceProblem = conformance.ConformanceProblem


# ID: 7be6a14e-f894-4691-9b5e-f807b17c8f95
def test_ConformanceProblem():
    problem = ConformanceProblem(
        rule="no_run_method", message="Engine lacks a run() method"
    )
    assert problem.rule == "no_run_method"
    assert problem.message == "Engine lacks a run() method"
    assert str(problem) == "no_run_method: Engine lacks a run() method"
