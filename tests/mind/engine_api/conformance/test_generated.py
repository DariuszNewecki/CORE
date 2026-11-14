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


from unittest.mock import patch


# ID: 197156b0-203c-4978-b139-d20de13ad146
def test_check_engine():
    import importlib
    import sys

    conformance = sys.modules.get("mind.engine_api.conformance")
    if conformance is None:
        conformance = importlib.import_module("mind.engine_api.conformance")

    check_engine = conformance.check_engine
    ConformanceProblem = conformance.ConformanceProblem

    # ID: ae26483a-24e2-4251-8fc7-c5530e50fa06
    class FakeEngine:
        pass

    FakeEngine.__module__ = "mind.logic.engines.fake_engine"

    with (
        patch("mind.engine_api.conformance.declaration_problems", return_value=[]),
        patch("mind.engine_api.conformance.api_version_problem", return_value=None),
        patch("mind.engine_api.conformance.engine_id_of", return_value="fake_engine"),
        patch("mind.engine_api.conformance.d6_problems", return_value=[]),
    ):
        problems = check_engine(FakeEngine)

    assert problems == []
    assert isinstance(problems, list)

    with (
        patch(
            "mind.engine_api.conformance.declaration_problems",
            return_value=["missing method"],
        ),
        patch(
            "mind.engine_api.conformance.api_version_problem",
            return_value="bad version",
        ),
        patch("mind.engine_api.conformance.engine_id_of", return_value="fake_engine"),
        patch("mind.engine_api.conformance.d6_problems", return_value=["d6 issue"]),
    ):
        problems = check_engine(FakeEngine)

    assert len(problems) == 3
    assert all(isinstance(p, ConformanceProblem) for p in problems)
